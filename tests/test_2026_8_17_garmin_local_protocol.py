"""Pure regression tests for independent Garmin GFDI protocol primitives."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "custom_components" / "fitness" / "device_adapters" / "garmin" / "protocol.py"
SPEC = importlib.util.spec_from_file_location("fitness_garmin_protocol_test", PROTOCOL_PATH)
assert SPEC is not None and SPEC.loader is not None
p = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = p
SPEC.loader.exec_module(p)


def _file_message(id1: int, id2: int, *, code: int, name: str | None, size: int, page: int) -> bytes:
    file_id = p.pb_fixed64(1, id1) + p.pb_fixed64(2, id2)
    file_type = p.pb_uint(3, code)
    if name is not None:
        file_type = p.pb_string(2, name) + file_type
    return (
        p.pb_bytes(1, file_id)
        + p.pb_bytes(2, file_type)
        + p.pb_uint(3, size)
        + p.pb_uint(5, page)
    )


def _list_response(*files: bytes, cursor: int | None = None, next_page: int | None = None) -> bytes:
    response = bytearray()
    if cursor is not None:
        response += p.pb_uint(2, cursor)
    if next_page is not None:
        response += p.pb_uint(3, next_page)
    for item in files:
        response += p.pb_bytes(4, item)
    return bytes(response)


def test_gfdi_crc_and_cobs_round_trip_in_arbitrary_notification_chunks():
    frame = p.build_gfdi(p.GFDI_CONFIGURATION, b"\x03\x00hello\x00garmin")
    kind, payload = p.parse_gfdi(frame)
    assert kind == p.GFDI_CONFIGURATION
    assert payload == b"\x03\x00hello\x00garmin"

    encoded = p.garmin_cobs_encode(frame)
    stream = p.GarminCobsStream()
    decoded = []
    for offset in range(0, len(encoded), 3):
        decoded.extend(stream.feed(encoded[offset : offset + 3]))
    assert decoded == [frame]

    damaged = bytearray(frame)
    damaged[-3] ^= 0x40
    with pytest.raises(p.GarminProtocolError, match="CRC"):
        p.parse_gfdi(bytes(damaged))


def test_protobuf_reassembler_is_bounded_overlap_safe_and_order_independent():
    data = b"0123456789abcdefghijklmnopqrstuvwxyz"
    request_id = 301

    def fragment(offset: int, body: bytes) -> bytes:
        return struct.pack("<HIII", request_id, offset, len(data), len(body)) + body

    assembler = p.ProtobufReassembler(max_size=128)
    _rid, complete = assembler.add(fragment(12, data[12:24]))
    assert complete is None
    _rid, complete = assembler.add(fragment(0, data[:18]))  # benign overlap 12..17
    assert complete is None
    _rid, complete = assembler.add(fragment(24, data[24:]))
    assert complete == data

    assembler = p.ProtobufReassembler(max_size=8)
    with pytest.raises(p.GarminProtocolLimitError):
        assembler.add(fragment(0, data[:1]))


def test_filesync_type_codes_are_resolved_per_response_not_globally():
    # Response 1: code 2 is FIT_TYPE_4 and the second file omits the repeated name.
    first = _list_response(
        _file_message(1, 11, code=2, name="FIT_TYPE_4", size=7000, page=100),
        _file_message(2, 22, code=2, name=None, size=8000, page=99),
        cursor=1,
    )
    # A separate response is allowed to reuse code 2 for another semantic type.
    second = _list_response(
        _file_message(3, 33, code=2, name="BACKUP_PRIMARY", size=9000, page=98),
        _file_message(4, 44, code=2, name=None, size=10000, page=97),
        next_page=123,
    )
    smart = p.pb_bytes(43, p.pb_bytes(10, first) + p.pb_bytes(10, second))

    files, cursor, next_page = p.parse_file_list_response(smart)
    assert [item.type_name for item in files] == [
        "FIT_TYPE_4",
        "FIT_TYPE_4",
        "BACKUP_PRIMARY",
        "BACKUP_PRIMARY",
    ]
    assert files[0].file_id.key != files[1].file_id.key
    assert cursor == 1
    assert next_page == 123


def test_file_request_is_read_only_and_round_trips_exact_returned_file_message():
    raw = _file_message(0x1234, 0x5678, code=7, name="FIT_TYPE_4", size=12345, page=77)
    item = p.GarminSyncFile(p.GarminFileId(0x1234, 0x5678), "FIT_TYPE_4", 7, 12345, 77, raw)
    request = p.build_file_request(item)
    file_sync = p.pb_first(request, 43, wire=2)
    file_request = p.pb_first(bytes(file_sync), 1, wire=2)
    assert p.pb_first(bytes(file_request), 1, wire=2) == raw
    assert p.pb_first(bytes(file_request), 2, wire=0) == 24
    assert p.pb_first(bytes(file_request), 3, wire=0) == 0
    assert p.pb_first(bytes(file_request), 4, wire=0) == 0
    assert p.pb_first(bytes(file_request), 5, wire=0) == 15


def test_legacy_directory_activity_detection_is_protocol_based():
    activity = struct.pack("<HBBHBBII", 207, 128, 4, 0, 0, 0, 7381, 1234)
    monitor = struct.pack("<HBBHBBII", 208, 128, 32, 0, 0, 0, 1703, 1235)
    entries = p.parse_directory(activity + monitor)
    assert entries[0].is_activity is True
    assert entries[1].is_activity is False
    assert entries[0].key.startswith("legacy:207:128:4:")

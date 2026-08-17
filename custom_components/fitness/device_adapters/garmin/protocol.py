"""Small, bounded Garmin GFDI protocol primitives.

This module intentionally contains no Home Assistant imports so its framing,
COBS, CRC and protobuf handling can be unit tested without starting HA.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any, Iterable

GARMIN_COMPANY_ID = 0x0087
GARMIN_ADVERTISEMENT_SERVICE_UUID = "0000fe1f-0000-1000-8000-00805f9b34fb"
GARMIN_UUID_SUFFIX = "-667b-11e3-949a-0800200c9a66"
GARMIN_GFDI_V2_SERVICE_UUID = f"6a4e2800{GARMIN_UUID_SUFFIX}"
GARMIN_GFDI_V1_SERVICE_UUID = f"6a4e2401{GARMIN_UUID_SUFFIX}"
GARMIN_GFDI_V1_SEND_UUID = f"6a4e4c80{GARMIN_UUID_SUFFIX}"
GARMIN_GFDI_V1_RECEIVE_UUID = f"6a4ecd28{GARMIN_UUID_SUFFIX}"
GARMIN_GFDI_V0_SERVICE_UUID = "9b012401-bc30-ce9a-e111-0f67e491abde"
GARMIN_GFDI_V0_SEND_UUID = "df334c80-e6a7-d082-274d-78fc66f85e16"
GARMIN_GFDI_V0_RECEIVE_UUID = "4acbcd28-7425-868e-f447-915c8f00d0cb"

GFDI_RESPONSE = 5000
GFDI_DOWNLOAD_REQUEST = 5002
GFDI_FILE_TRANSFER_DATA = 5004
GFDI_DEVICE_INFORMATION = 5024
GFDI_DEVICE_SETTINGS = 5026
GFDI_SYSTEM_EVENT = 5030
GFDI_SUPPORTED_FILE_TYPES_REQUEST = 5031
GFDI_NOTIFICATION_SUBSCRIPTION = 5036
GFDI_MUSIC_CONTROL_CAPABILITIES = 5042
GFDI_PROTOBUF_REQUEST = 5043
GFDI_PROTOBUF_RESPONSE = 5044
GFDI_CONFIGURATION = 5050
GFDI_CURRENT_TIME_REQUEST = 5052
GFDI_AUTH_NEGOTIATION = 5101

STATUS_ACK = 0
STATUS_NAK = 1
STATUS_UNSUPPORTED = 2

# Resource ceilings are deliberately protocol-level, not device-model-specific.
MAX_GFDI_FRAME_BYTES = 256 * 1024
MAX_COBS_BUFFER_BYTES = 512 * 1024
MAX_PROTOBUF_BYTES = 4 * 1024 * 1024
MAX_PROTOBUF_FIELDS = 20_000
MAX_FILE_LIST_ITEMS = 2_000

GARMIN_EPOCH_OFFSET = 631065600


class GarminProtocolError(RuntimeError):
    """Malformed or rejected Garmin protocol data."""


class GarminProtocolLimitError(GarminProtocolError):
    """Incoming data exceeded a defensive resource ceiling."""


class GarminUnsupportedTransport(GarminProtocolError):
    """The watch exposed a transport mode this backend cannot safely use."""


def crc16(data: bytes | bytearray | memoryview, initial: int = 0) -> int:
    """Return the reflected CRC-16 used by Garmin GFDI/FIT framing.

    A bitwise implementation keeps this independent from any third-party
    project and avoids allocating a lookup table in the BLE hot path.
    """
    crc = int(initial) & 0xFFFF
    for byte in bytes(data):
        crc ^= byte
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF


def build_gfdi(message_type: int, payload: bytes = b"") -> bytes:
    """Build one complete little-endian GFDI frame."""
    body = bytearray(b"\x00\x00")
    body += struct.pack("<H", int(message_type) & 0xFFFF)
    body += bytes(payload)
    total = len(body) + 2
    if total > MAX_GFDI_FRAME_BYTES:
        raise GarminProtocolLimitError("GFDI frame exceeds safe size")
    struct.pack_into("<H", body, 0, total)
    body += struct.pack("<H", crc16(body))
    return bytes(body)


def parse_gfdi(frame: bytes) -> tuple[int, bytes]:
    """Validate and unpack one complete GFDI frame."""
    frame = bytes(frame)
    if len(frame) < 6:
        raise GarminProtocolError("GFDI frame is truncated")
    if len(frame) > MAX_GFDI_FRAME_BYTES:
        raise GarminProtocolLimitError("GFDI frame exceeds safe size")
    declared = struct.unpack_from("<H", frame, 0)[0]
    if declared != len(frame):
        raise GarminProtocolError("GFDI frame length mismatch")
    expected = struct.unpack_from("<H", frame, len(frame) - 2)[0]
    actual = crc16(frame[:-2])
    if expected != actual:
        raise GarminProtocolError("GFDI CRC mismatch")
    message_type = struct.unpack_from("<H", frame, 2)[0]
    return message_type, frame[4:-2]


def build_generic_status(original_type: int, status: int = STATUS_ACK, extra: bytes = b"") -> bytes:
    return build_gfdi(
        GFDI_RESPONSE,
        struct.pack("<HB", int(original_type) & 0xFFFF, int(status) & 0xFF) + bytes(extra),
    )


def cobs_encode(data: bytes) -> bytes:
    """Encode standard COBS bytes (without delimiters)."""
    source = bytes(data)
    out = bytearray()
    code_index = 0
    out.append(0)
    code = 1
    for byte in source:
        if byte == 0:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
            continue
        out.append(byte)
        code += 1
        if code == 0xFF:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
    out[code_index] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    """Decode standard COBS bytes (without delimiters)."""
    source = bytes(data)
    if not source:
        raise GarminProtocolError("empty COBS body")
    out = bytearray()
    index = 0
    while index < len(source):
        code = source[index]
        if code == 0:
            raise GarminProtocolError("zero inside COBS body")
        index += 1
        end = index + code - 1
        if end > len(source):
            raise GarminProtocolError("COBS block exceeds packet")
        out.extend(source[index:end])
        index = end
        if code != 0xFF and index < len(source):
            out.append(0)
    return bytes(out)


def garmin_cobs_encode(frame: bytes) -> bytes:
    """Garmin's stream form adds a zero delimiter at both ends."""
    return b"\x00" + cobs_encode(frame) + b"\x00"


class GarminCobsStream:
    """Incrementally decode Garmin-delimited COBS frames with a hard cap."""

    def __init__(self, max_buffer: int = MAX_COBS_BUFFER_BYTES) -> None:
        self.max_buffer = max(64, int(max_buffer))
        self._encoded = bytearray()

    def reset(self) -> None:
        self._encoded.clear()

    def feed(self, data: bytes | bytearray) -> list[bytes]:
        frames: list[bytes] = []
        for byte in bytes(data):
            if byte == 0:
                if not self._encoded:
                    continue
                encoded = bytes(self._encoded)
                self._encoded.clear()
                decoded = cobs_decode(encoded)
                if len(decoded) > MAX_GFDI_FRAME_BYTES:
                    raise GarminProtocolLimitError("decoded GFDI frame exceeds safe size")
                frames.append(decoded)
                continue
            self._encoded.append(byte)
            if len(self._encoded) > self.max_buffer:
                self._encoded.clear()
                raise GarminProtocolLimitError("COBS receive buffer exceeded safe size")
        return frames


# ---- Tiny protobuf codec -------------------------------------------------

def pb_varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        raise ValueError("protobuf varint must be non-negative")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def pb_key(field: int, wire: int) -> bytes:
    return pb_varint((int(field) << 3) | int(wire))


def pb_uint(field: int, value: int) -> bytes:
    return pb_key(field, 0) + pb_varint(value)


def pb_fixed64(field: int, value: int) -> bytes:
    return pb_key(field, 1) + struct.pack("<Q", int(value) & 0xFFFFFFFFFFFFFFFF)


def pb_bytes(field: int, value: bytes) -> bytes:
    value = bytes(value)
    return pb_key(field, 2) + pb_varint(len(value)) + value


def pb_string(field: int, value: str) -> bytes:
    return pb_bytes(field, value.encode("utf-8"))


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while offset < len(data) and shift <= 63:
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, offset
        shift += 7
    raise GarminProtocolError("invalid protobuf varint")


def pb_decode(data: bytes, *, max_fields: int = MAX_PROTOBUF_FIELDS) -> dict[int, list[tuple[int, Any]]]:
    """Decode enough protobuf wire types for Garmin FileSync messages."""
    data = bytes(data)
    if len(data) > MAX_PROTOBUF_BYTES:
        raise GarminProtocolLimitError("protobuf exceeds safe size")
    result: dict[int, list[tuple[int, Any]]] = {}
    offset = 0
    field_count = 0
    while offset < len(data):
        field_count += 1
        if field_count > max_fields:
            raise GarminProtocolLimitError("protobuf field count exceeds safe limit")
        key, offset = _read_varint(data, offset)
        field = key >> 3
        wire = key & 0x07
        if field <= 0:
            raise GarminProtocolError("invalid protobuf field number")
        if wire == 0:
            value, offset = _read_varint(data, offset)
        elif wire == 1:
            if offset + 8 > len(data):
                raise GarminProtocolError("truncated protobuf fixed64")
            value = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
        elif wire == 2:
            length, offset = _read_varint(data, offset)
            end = offset + length
            if length > MAX_PROTOBUF_BYTES or end > len(data):
                raise GarminProtocolError("truncated protobuf bytes field")
            value = data[offset:end]
            offset = end
        elif wire == 5:
            if offset + 4 > len(data):
                raise GarminProtocolError("truncated protobuf fixed32")
            value = struct.unpack_from("<I", data, offset)[0]
            offset += 4
        else:
            raise GarminProtocolError(f"unsupported protobuf wire type {wire}")
        result.setdefault(field, []).append((wire, value))
    return result


def pb_values(message: bytes, field: int, *, wire: int | None = None) -> list[Any]:
    values = []
    for item_wire, value in pb_decode(message).get(int(field), []):
        if wire is None or item_wire == wire:
            values.append(value)
    return values


def pb_first(message: bytes, field: int, *, wire: int | None = None) -> Any:
    values = pb_values(message, field, wire=wire)
    return values[0] if values else None


@dataclass(slots=True, frozen=True)
class GarminFileId:
    id1: int
    id2: int

    @property
    def key(self) -> str:
        return f"{self.id1:016x}:{self.id2:016x}"


@dataclass(slots=True)
class GarminSyncFile:
    file_id: GarminFileId
    type_name: str | None
    type_code: int | None
    size: int
    page_id: int | None
    raw: bytes


@dataclass(slots=True)
class GarminDirectoryEntry:
    index: int
    data_type: int
    sub_type: int
    number: int
    specific_flags: int
    file_flags: int
    size: int
    timestamp: int

    @property
    def is_activity(self) -> bool:
        return self.data_type == 128 and self.sub_type == 4

    @property
    def key(self) -> str:
        return f"legacy:{self.index}:{self.data_type}:{self.sub_type}:{self.number}:{self.timestamp}"


def encode_file_id(file_id: GarminFileId) -> bytes:
    return pb_fixed64(1, file_id.id1) + pb_fixed64(2, file_id.id2)


def build_file_list_request(*, cursor_id: int | None = None, start_page_id: int | None = None) -> bytes:
    """Build read-only FileSyncService list request.

    Synced-file exclusion flags are intentionally omitted so HA-Fitness can see
    history without changing the watch's Garmin-Connect sync state.
    """
    request = bytearray()
    if cursor_id is not None:
        request += pb_uint(1, cursor_id)
    elif start_page_id is not None:
        request += pb_uint(2, start_page_id)
    file_sync = pb_bytes(9, bytes(request))
    return pb_bytes(43, file_sync)


def _parse_file_type(data: bytes) -> tuple[int | None, str | None]:
    code = pb_first(data, 3, wire=0)
    name_raw = pb_first(data, 2, wire=2)
    name = None
    if isinstance(name_raw, (bytes, bytearray)):
        name = bytes(name_raw).decode("utf-8", errors="replace")[:128]
    return (int(code) if code is not None else None, name)


def _parse_file_id(data: bytes) -> GarminFileId | None:
    id1 = pb_first(data, 1, wire=1)
    id2 = pb_first(data, 2, wire=1)
    if id1 is None or id2 is None:
        return None
    return GarminFileId(int(id1), int(id2))


def parse_file_list_response(smart: bytes) -> tuple[list[GarminSyncFile], int | None, int | None]:
    """Parse one Smart/FileSync FileListResponse, resolving type names per response."""
    file_sync_values = pb_values(smart, 43, wire=2)
    responses: list[bytes] = []
    for file_sync in file_sync_values:
        responses.extend(pb_values(bytes(file_sync), 10, wire=2))
    if not responses:
        raise GarminProtocolError("protobuf contains no FileListResponse")

    all_files: list[GarminSyncFile] = []
    cursor: int | None = None
    next_page: int | None = None
    for response in responses:
        response = bytes(response)
        response_cursor = pb_first(response, 2, wire=0)
        response_next = pb_first(response, 3, wire=0)
        if response_cursor is not None:
            cursor = int(response_cursor)
        if response_next is not None:
            next_page = int(response_next)
        raw_files = [bytes(x) for x in pb_values(response, 4, wire=2)]
        if len(raw_files) > MAX_FILE_LIST_ITEMS:
            raise GarminProtocolLimitError("FileSync response contains too many files")
        type_names: dict[int, str] = {}
        parsed: list[tuple[bytes, GarminFileId, int | None, str | None, int, int | None]] = []
        for raw in raw_files:
            file_id_raw = pb_first(raw, 1, wire=2)
            type_raw = pb_first(raw, 2, wire=2)
            if not isinstance(file_id_raw, (bytes, bytearray)):
                continue
            file_id = _parse_file_id(bytes(file_id_raw))
            if file_id is None:
                continue
            type_code: int | None = None
            type_name: str | None = None
            if isinstance(type_raw, (bytes, bytearray)):
                type_code, type_name = _parse_file_type(bytes(type_raw))
                if type_code is not None and type_name:
                    type_names[type_code] = type_name
            size = int(pb_first(raw, 3, wire=0) or 0)
            page = pb_first(raw, 5, wire=0)
            parsed.append((raw, file_id, type_code, type_name, size, int(page) if page is not None else None))
        for raw, file_id, type_code, type_name, size, page in parsed:
            if not type_name and type_code is not None:
                type_name = type_names.get(type_code)
            all_files.append(GarminSyncFile(file_id, type_name, type_code, size, page, raw))
    return all_files, cursor, next_page


def build_file_request(file: GarminSyncFile) -> bytes:
    """Build read-only FileSyncService FileRequest for an exact returned record."""
    request = bytearray()
    request += pb_bytes(1, bytes(file.raw))
    request += pb_uint(2, 24)
    request += pb_uint(3, 0)
    request += pb_uint(4, 0)
    request += pb_uint(5, 15)
    file_sync = pb_bytes(1, bytes(request))
    return pb_bytes(43, file_sync)


def parse_file_response(smart: bytes) -> tuple[int, int | None]:
    """Return (status, temporary handle) from FileSyncService FileResponse."""
    for file_sync in pb_values(smart, 43, wire=2):
        for response in pb_values(bytes(file_sync), 2, wire=2):
            status = pb_first(bytes(response), 1, wire=0)
            handle = pb_first(bytes(response), 3, wire=0)
            if status is not None:
                return int(status), int(handle) if handle is not None else None
    raise GarminProtocolError("protobuf contains no FileResponse")


def build_protobuf_message(message_type: int, request_id: int, protobuf: bytes) -> bytes:
    protobuf = bytes(protobuf)
    if len(protobuf) > MAX_PROTOBUF_BYTES:
        raise GarminProtocolLimitError("protobuf request exceeds safe size")
    wrapper = struct.pack("<HIII", int(request_id) & 0xFFFF, 0, len(protobuf), len(protobuf))
    return build_gfdi(message_type, wrapper + protobuf)


def parse_protobuf_wrapper(payload: bytes) -> tuple[int, int, int, bytes]:
    if len(payload) < 14:
        raise GarminProtocolError("protobuf GFDI wrapper is truncated")
    request_id, offset, total, length = struct.unpack_from("<HIII", payload, 0)
    if total > MAX_PROTOBUF_BYTES or length > MAX_PROTOBUF_BYTES:
        raise GarminProtocolLimitError("protobuf response exceeds safe size")
    if len(payload) != 14 + length:
        raise GarminProtocolError("protobuf wrapper length mismatch")
    if offset + length > total:
        raise GarminProtocolError("protobuf fragment lies outside declared total")
    return request_id, offset, total, payload[14:]


def build_protobuf_chunk_ack(request_id: int, offset: int) -> bytes:
    # RESPONSE(original type, ACK, request id, received offset, KEPT, NO_ERROR)
    extra = struct.pack("<HIBB", int(request_id) & 0xFFFF, int(offset), 0, 0)
    return build_generic_status(GFDI_PROTOBUF_RESPONSE, STATUS_ACK, extra)


class ProtobufReassembler:
    """Bounded, overlap-safe reassembler for one Garmin protobuf request id."""

    def __init__(self, max_size: int = MAX_PROTOBUF_BYTES) -> None:
        self.max_size = int(max_size)
        self.reset()

    def reset(self) -> None:
        self.request_id: int | None = None
        self.total: int | None = None
        self._data: bytearray | None = None
        self._seen: bytearray | None = None
        self._received = 0

    def add(self, payload: bytes) -> tuple[int, bytes | None]:
        request_id, offset, total, fragment = parse_protobuf_wrapper(payload)
        if total > self.max_size:
            raise GarminProtocolLimitError("protobuf reassembly exceeds safe limit")
        if self.request_id is None:
            self.request_id = request_id
            self.total = total
            self._data = bytearray(total)
            self._seen = bytearray(total)
        elif request_id != self.request_id or total != self.total:
            raise GarminProtocolError("interleaved protobuf responses are not supported")
        assert self._data is not None and self._seen is not None and self.total is not None
        for index, byte in enumerate(fragment, start=offset):
            if self._seen[index]:
                if self._data[index] != byte:
                    raise GarminProtocolError("conflicting protobuf overlap")
                continue
            self._data[index] = byte
            self._seen[index] = 1
            self._received += 1
        if self._received == self.total:
            complete = bytes(self._data)
            result_id = int(self.request_id)
            self.reset()
            return result_id, complete
        return request_id, None


def parse_directory(data: bytes) -> list[GarminDirectoryEntry]:
    if len(data) % 16:
        raise GarminProtocolError("Garmin directory length is not a multiple of 16")
    entries: list[GarminDirectoryEntry] = []
    for offset in range(0, len(data), 16):
        index, data_type, sub_type, number, specific, flags, size, timestamp = struct.unpack_from(
            "<HBBHBBII", data, offset
        )
        entries.append(
            GarminDirectoryEntry(index, data_type, sub_type, number, specific, flags, size, timestamp)
        )
        if len(entries) > MAX_FILE_LIST_ITEMS:
            raise GarminProtocolLimitError("legacy Garmin directory is too large")
    return entries


def build_download_request(index: int, *, offset: int = 0, request_new: bool = True, crc_seed: int = 0) -> bytes:
    payload = struct.pack(
        "<HIBHI",
        int(index) & 0xFFFF,
        int(offset) & 0xFFFFFFFF,
        1 if request_new else 0,
        int(crc_seed) & 0xFFFF,
        0,
    )
    return build_gfdi(GFDI_DOWNLOAD_REQUEST, payload)


def parse_download_status(payload: bytes) -> tuple[int, int, int]:
    """Parse RESPONSE payload for DOWNLOAD_REQUEST."""
    if len(payload) < 8:
        raise GarminProtocolError("download response is truncated")
    original, status, download_status, size = struct.unpack_from("<HBBI", payload, 0)
    if original != GFDI_DOWNLOAD_REQUEST:
        raise GarminProtocolError("response is not for DOWNLOAD_REQUEST")
    return status, download_status, size


def parse_file_transfer(payload: bytes) -> tuple[int, int, bytes]:
    if len(payload) < 7:
        raise GarminProtocolError("file transfer chunk is truncated")
    _flags, running_crc, offset = struct.unpack_from("<BHI", payload, 0)
    return running_crc, offset, payload[7:]


def build_file_transfer_ack(next_offset: int) -> bytes:
    # transfer status 0 == OK
    return build_generic_status(
        GFDI_FILE_TRANSFER_DATA,
        STATUS_ACK,
        struct.pack("<BI", 0, int(next_offset) & 0xFFFFFFFF),
    )

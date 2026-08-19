"""Pure capability tests for model-independent Garmin transport selection."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import struct
import types

ROOT = Path(__file__).resolve().parents[1]
GARMIN = ROOT / "custom_components" / "fitness" / "device_adapters" / "garmin"
PACKAGE = "fitness_garmin_capability_test"

pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(GARMIN)]
sys.modules[PACKAGE] = pkg

for module_name in ("protocol", "gfdi"):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{module_name}", GARMIN / f"{module_name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

p = sys.modules[f"{PACKAGE}.protocol"]
g = sys.modules[f"{PACKAGE}.gfdi"]


class _Char:
    def __init__(self, uuid: str, properties=()):
        self.uuid = uuid
        self.properties = list(properties)


class _Service:
    def __init__(self, characteristics):
        self.characteristics = list(characteristics)


class _Client:
    def __init__(self, characteristics):
        self.services = [_Service(characteristics)]


def test_v2_channel_nibble_is_capability_discovered_not_product_mapped():
    client = _Client(
        [
            _Char(f"6A4E281F{p.GARMIN_UUID_SUFFIX}", ["notify"]),
            _Char(f"6A4E282F{p.GARMIN_UUID_SUFFIX}", ["write-without-response"]),
        ]
    )
    candidates = g.transport_candidates_from_client(client)
    assert [candidate.backend for candidate in candidates] == ["gfdi_v2_ml"]
    assert candidates[0].receive_uuid.startswith("6a4e281f")
    assert candidates[0].send_uuid.startswith("6a4e282f")
    assert candidates[0].write_with_response is False


def test_mixed_device_capabilities_offer_v2_then_v1_then_v0_fallbacks():
    client = _Client(
        [
            _Char(f"6a4e2810{p.GARMIN_UUID_SUFFIX}", ["indicate"]),
            _Char(f"6a4e2820{p.GARMIN_UUID_SUFFIX}", ["write"]),
            _Char(p.GARMIN_GFDI_V1_RECEIVE_UUID, ["notify"]),
            _Char(p.GARMIN_GFDI_V1_SEND_UUID, ["write"]),
            _Char(p.GARMIN_GFDI_V0_RECEIVE_UUID, ["notify"]),
            _Char(p.GARMIN_GFDI_V0_SEND_UUID, ["write"]),
        ]
    )
    assert [candidate.backend for candidate in g.transport_candidates_from_client(client)] == [
        "gfdi_v2_ml",
        "gfdi_v1",
        "gfdi_v0",
    ]
    assert g.transport_capabilities_from_client(client) == (
        "gfdi_v2_ml",
        "gfdi_v1",
        "gfdi_v0",
    )
    assert all(candidate.write_with_response is True for candidate in g.transport_candidates_from_client(client))


def test_incomplete_or_wrong_property_pairs_are_rejected_without_guessing():
    incomplete = _Client([_Char(f"6a4e281a{p.GARMIN_UUID_SUFFIX}", ["notify"])])
    assert g.transport_candidates_from_client(incomplete) == ()

    wrong_props = _Client(
        [
            _Char(f"6a4e281a{p.GARMIN_UUID_SUFFIX}", ["read"]),
            _Char(f"6a4e282a{p.GARMIN_UUID_SUFFIX}", ["read"]),
        ]
    )
    assert g.transport_candidates_from_client(wrong_props) == ()


def test_v2_candidate_count_is_bounded_even_if_many_channel_pairs_are_exposed():
    chars = []
    for channel in "0123456789abcdef":
        chars.extend(
            [
                _Char(f"6a4e281{channel}{p.GARMIN_UUID_SUFFIX}", ["notify"]),
                _Char(f"6a4e282{channel}{p.GARMIN_UUID_SUFFIX}", ["write"]),
            ]
        )
    candidates = g.transport_candidates_from_client(_Client(chars))
    assert len(candidates) == g.MAX_V2_CHANNEL_CANDIDATES
    assert len(candidates) <= g.MAX_TRANSPORT_CANDIDATES


def test_v2_close_all_request_has_exact_multilink_wire_length():
    transport = g.GarminV2Transport(
        _Client([]),
        f"6a4e2810{p.GARMIN_UUID_SUFFIX}",
        f"6a4e2820{p.GARMIN_UUID_SUFFIX}",
    )
    # V2 CLOSE_ALL uses uint16 flags plus one reserved trailing byte.
    close_all = transport._management_request(5, b"\x00\x00\x00")
    assert len(close_all) == 13
    assert close_all[:2] == b"\x00\x05"
    assert struct.unpack_from("<Q", close_all, 2)[0] == g.V2_CLIENT_ID
    assert close_all[-3:] == b"\x00\x00\x00"


def test_v2_register_success_accepts_optional_reliable_byte_omission():
    transport = g.GarminV2Transport(
        _Client([]),
        f"6a4e2810{p.GARMIN_UUID_SUFFIX}",
        f"6a4e2820{p.GARMIN_UUID_SUFFIX}",
    )
    # Body is notification payload after the leading management handle 0x00.
    compact = bytes([1]) + struct.pack("<QHBB", g.V2_CLIENT_ID, g.V2_GFDI_SERVICE, 0, 0x42)
    assert len(compact) == 13
    transport._observe_management(compact)
    assert transport._gfdi_handle == 0x42
    assert transport._service_by_handle[0x42] == g.V2_GFDI_SERVICE

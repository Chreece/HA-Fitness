"""Pure capability tests for model-independent Garmin transport selection."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
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

"""Native sensor vendor handling must be entirely catalog-driven."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "custom_components/fitness/live"
CATALOG = json.loads((LIVE / "device_catalog.json").read_text(encoding="utf-8"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_catalog_contains_product_selected_vendor_decoders():
    assert CATALOG["version"] >= 2
    assert isinstance(CATALOG.get("vendor_decoders"), list)
    decoder_ids = {
        item["id"] for item in CATALOG["vendor_decoders"] if isinstance(item, dict)
    }
    assert decoder_ids
    for product in CATALOG["products"]:
        for decoder_id in product.get("decoder_ids", []):
            assert decoder_id in decoder_ids


def test_native_python_has_no_known_vendor_names_or_company_ids():
    # Vendor names/IDs are allowed only in the JSON catalog. Runtime code,
    # ANT, BLE and identity logic must stay product-agnostic.
    forbidden = (
        "stryd", "garmin", "wahoo", "polar", "coros", "suunto",
        "coospo", "favero", "assioma", "4iiii", "magene", "igpsport",
        "bryton", "tacx", "elite", "stages", "hammerhead",
        "43690",
    )
    for path in LIVE.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token.lower() not in text, f"{token!r} leaked into {path.relative_to(ROOT)}"


def test_generic_manager_sport_inference_has_no_device_names():
    manager = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
    block = manager.split("def _infer_sport", 1)[1].split("def _workout_name", 1)[0]
    assert "stryd" not in block.lower()
    assert "running_power" in block
    assert "bike_power" in block


def test_bluetooth_transport_delegates_proprietary_payloads_to_registry():
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    assert "decode_bluetooth_advertisement(info)" in bt
    assert "manufacturer_data.get(" not in bt.split(
        "def _passive_advertisement_values", 1
    )[1].split("@dataclass", 1)[0]


def test_ant_manufacturer_names_are_catalog_resolved():
    ant_const = (LIVE / "antplus_core/const.py").read_text(encoding="utf-8")
    receiver = (LIVE / "antplus_core/receiver.py").read_text(encoding="utf-8")
    assert "MANUFACTURERS =" not in ant_const
    assert 'catalog_manufacturer_name("antplus", manufacturer_id)' in receiver


def test_catalog_vendor_decoder_can_decode_current_proprietary_example():
    # Load package modules normally through a temporary package namespace.
    # This verifies the byte offset lives in JSON rather than bluetooth.py.
    import sys
    import types

    pkg = types.ModuleType("custom_components")
    pkg.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", pkg)
    fitness = types.ModuleType("custom_components.fitness")
    fitness.__path__ = [str(ROOT / "custom_components/fitness")]
    sys.modules.setdefault("custom_components.fitness", fitness)
    live_pkg = types.ModuleType("custom_components.fitness.live")
    live_pkg.__path__ = [str(LIVE)]
    sys.modules.setdefault("custom_components.fitness.live", live_pkg)

    identity = _load_module(
        "custom_components.fitness.live.device_identity",
        LIVE / "device_identity.py",
    )
    sys.modules["custom_components.fitness.live.device_identity"] = identity
    registry = _load_module(
        "custom_components.fitness.live.vendor_registry",
        LIVE / "vendor_registry.py",
    )

    info = SimpleNamespace(
        name="StrydX",
        manufacturer_data={43690: bytes([0, 87])},
        service_data={},
        service_uuids=[],
    )
    values, metadata = registry.decode_bluetooth_advertisement(info)
    assert values["battery"] == 87.0
    assert metadata["battery"]["decoder_id"] == "stryd_ble_passive_battery_v1"


def test_vendor_registry_catalog_has_no_consistency_issues():
    import sys
    import types

    pkg = types.ModuleType("custom_components")
    pkg.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", pkg)
    fitness = types.ModuleType("custom_components.fitness")
    fitness.__path__ = [str(ROOT / "custom_components/fitness")]
    sys.modules.setdefault("custom_components.fitness", fitness)
    live_pkg = types.ModuleType("custom_components.fitness.live")
    live_pkg.__path__ = [str(LIVE)]
    sys.modules.setdefault("custom_components.fitness.live", live_pkg)

    identity = _load_module(
        "custom_components.fitness.live.device_identity",
        LIVE / "device_identity.py",
    )
    sys.modules["custom_components.fitness.live.device_identity"] = identity
    registry = _load_module(
        "custom_components.fitness.live.vendor_registry",
        LIVE / "vendor_registry.py",
    )
    assert registry.vendor_registry_issues() == []

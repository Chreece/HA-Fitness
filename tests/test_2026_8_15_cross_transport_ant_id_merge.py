import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_PATH = ROOT / "custom_components/fitness/live/device_identity.py"
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
CATALOG = json.loads((ROOT / "custom_components/fitness/live/device_catalog.json").read_text())


def _identity_module():
    spec = importlib.util.spec_from_file_location("fitness_device_identity_test", IDENTITY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_explicit_ant_device_number_is_a_generic_cross_transport_identity():
    identity = _identity_module()
    bt = identity.catalog_cross_transport_ids(
        "Any BLE HR sensor",
        "bluetooth",
        {"ant_device_number": 53248},
        {"heart_rate"},
    )
    ant = identity.catalog_cross_transport_ids(
        "Heart Rate Sensor",
        "antplus",
        {"device_number": 53248, "profiles": [120], "manufacturer_id": 1},
        {"heart_rate"},
    )
    assert ("explicit_ant_id", "ant_device_number:heart_rate", "53248") in bt
    assert bt & ant


def test_same_numeric_ant_id_is_scoped_by_capability():
    identity = _identity_module()
    hr = identity.catalog_cross_transport_ids(
        "HR", "bluetooth", {"ant_id": 1234}, {"heart_rate"}
    )
    power = identity.catalog_cross_transport_ids(
        "Power", "antplus", {"device_number": 1234}, {"power"}
    )
    assert not (hr & power)


def test_vendor_specific_ant_id_extraction_rules_live_in_catalog_not_runtime():
    rules = CATALOG.get("cross_transport_identity_rules") or []
    garmin = next(rule for rule in rules if rule.get("id") == "garmin_wearable_hr_ant_id")
    assert garmin["roles"]["antplus"]["manufacturer_id"] == 1
    assert garmin["roles"]["antplus"]["profiles"] == [120]
    assert any(
        spec.get("source") == "ant_device_number"
        for spec in garmin["roles"]["bluetooth"]["extractors"]
    )
    assert "garmin" not in RUNTIME.lower()


def test_exact_cross_transport_id_is_checked_before_serial_and_catalog_fallback():
    block = RUNTIME.split("def _match_sensor", 1)[1].split("@staticmethod", 1)[0]
    assert "catalog_cross_transport_ids" in block
    assert block.index("cross_ids = catalog_cross_transport_ids") < block.index("serial = _serial")
    assert block.index("serial = _serial") < block.index("family = catalog_product_id")
    assert 'matched.metadata["merge_evidence"] = "exact_cross_transport_id"' in block

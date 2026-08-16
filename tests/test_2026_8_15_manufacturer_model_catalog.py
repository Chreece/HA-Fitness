from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "custom_components/fitness/live/device_catalog.json"
IDENTITY_PATH = ROOT / "custom_components/fitness/live/device_identity.py"
BLUETOOTH_PATH = ROOT / "custom_components/fitness/live/bluetooth.py"
RUNTIME_PATH = ROOT / "custom_components/fitness/live/runtime.py"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

spec = importlib.util.spec_from_file_location("fitness_device_identity_catalog_test", IDENTITY_PATH)
assert spec and spec.loader
identity_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity_module)
resolve_identity = identity_module.resolve_identity


def _endpoint(transport: str, metadata: dict):
    return SimpleNamespace(transport=transport, metadata=metadata)


def _sensor(*, endpoints: dict, name: str = "Fitness sensor", caps=None):
    return SimpleNamespace(
        name=name,
        metadata={},
        endpoints=endpoints,
        capabilities=set(caps or {"power"}),
    )


def _ant_sensor(*, manufacturer_id: int, model_no: int, name: str = "Power Meter"):
    return _sensor(
        name=name,
        endpoints={
            "antplus": _endpoint(
                "antplus",
                {
                    "manufacturer_id": manufacturer_id,
                    "model_no": model_no,
                    "profiles": [11],
                },
            )
        },
    )


def _stryd_bt(model: str = "26"):
    return _sensor(
        name="Stryd",
        caps={"power", "speed", "distance", "cadence"},
        endpoints={
            "bluetooth": _endpoint(
                "bluetooth",
                {
                    "manufacturer_data_ids": [43690],
                    "manufacturer": "Stryd",
                    "model": model,
                    "identity_source": "gatt_device_information",
                },
            )
        },
    )


def test_stryd_model_catalog_is_manufacturer_scoped_source_driven_and_range_based() -> None:
    catalog = CATALOG["model_catalog"]["stryd"]
    assert catalog["manufacturer"] == "Stryd"
    assert catalog["manufacturer_match"]["antplus_manufacturer_ids"] == [95]
    assert catalog["manufacturer_match"]["bluetooth_manufacturer_data_ids"] == [43690]
    sources = {item["source"] for item in catalog["model_id_sources"]}
    assert sources == {"bluetooth_gatt_model_number", "antplus_model_no", "resolved_model_id"}
    assert {entry["name"] for entry in catalog["models"]} >= {
        "Stryd (chest mounted)",
        "Stryd (non-wind model)",
        "Stryd (wind model)",
        "Next Gen Stryd",
        "Stryd 5.0",
    }


def test_bt_gatt_model_26_names_next_gen_stryd_before_acceptance() -> None:
    identity = resolve_identity(_stryd_bt("26"))
    assert identity["manufacturer"] == "Stryd"
    assert identity["model_id"] == "26"
    assert identity["model"] == "Next Gen Stryd"
    assert identity["name"] == "Next Gen Stryd"
    assert identity["model_id_source"] == "bluetooth_gatt_model_number"
    assert identity["release"] == "Fall 2022"
    assert identity["paired_product_name"] == "Stryd Duo"


def test_ant_model_26_can_name_next_gen_when_protocol_reports_same_generation_id() -> None:
    identity = resolve_identity(_ant_sensor(manufacturer_id=95, model_no=26))
    assert identity["model_id"] == "26"
    assert identity["name"] == "Next Gen Stryd"
    assert identity["model_id_source"] == "antplus_model_no"


def test_large_ant_protocol_model_is_not_misclassified_as_stryd_5() -> None:
    identity = resolve_identity(_ant_sensor(manufacturer_id=95, model_no=4660))
    assert identity["name"] != "Stryd 5.0"
    assert identity.get("model") != "Stryd 5.0"


def test_bt_model_30_names_stryd_5() -> None:
    identity = resolve_identity(_stryd_bt("30"))
    assert identity["model"] == "Stryd 5.0"
    assert identity["name"] == "Stryd 5.0"
    assert identity["paired_product_name"] == "Stryd Duo 5.0"


def test_merged_bt_26_wins_over_unrelated_large_ant_protocol_model() -> None:
    sensor = _sensor(
        name="Stryd",
        endpoints={
            "bluetooth": _stryd_bt("26").endpoints["bluetooth"],
            "antplus": _endpoint(
                "antplus",
                {"manufacturer_id": 95, "model_no": 4660, "profiles": [11, 124]},
            ),
        },
        caps={"power", "speed", "distance", "cadence"},
    )
    identity = resolve_identity(sensor)
    assert identity["model_id"] == "26"
    assert identity["name"] == "Next Gen Stryd"


def test_model_number_is_never_global_without_matching_manufacturer() -> None:
    identity = resolve_identity(_ant_sensor(manufacturer_id=1, model_no=26, name="Heart Rate Sensor"))
    assert identity["name"] != "Next Gen Stryd"
    assert identity.get("model") != "Next Gen Stryd"


def test_duo_is_metadata_not_inferred_for_one_physical_pod() -> None:
    identity = resolve_identity(_stryd_bt("27"))
    assert identity["name"] == "Next Gen Stryd"
    assert identity["name"] != "Stryd Duo"
    assert identity["paired_product_name"] == "Stryd Duo"


def test_bluetooth_pnp_product_id_is_diagnostic_not_ha_model_id() -> None:
    source = BLUETOOTH_PATH.read_text(encoding="utf-8")
    assert 'metadata.setdefault("model_id", f"0x{product_id:04X}")' not in source
    assert '"bluetooth_product_id": product_id' in source


def test_discovery_flow_reopens_when_verified_identity_changes_name() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    assert "def _refresh_provisional_discovery_flow" in source
    assert "identity_name_changed" in source
    assert "self._refresh_provisional_discovery_flow(sensor.sensor_id)" in source


def test_ant_arrival_can_reprobe_unaccepted_recent_bt_candidate() -> None:
    source = BLUETOOTH_PATH.read_text(encoding="utf-8")
    block = source[source.index("def schedule_identity_probe_candidates"):source.index("def _schedule_identity_probe", source.index("def schedule_identity_probe_candidates"))]
    assert "sensor_is_accepted" not in block
    assert "sensor_recently_observed" in block


def test_runtime_re_resolves_persisted_sensor_names_on_startup() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    assert "Re-resolve persisted names through the current data catalog" in source
    assert "identity = resolve_identity(sensor)" in source
    assert "sensor.name = resolved_name" in source

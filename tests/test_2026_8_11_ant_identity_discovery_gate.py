"""ANT discovery uses RF confirmation while identity remains merge enrichment."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    ROOT / "custom_components/fitness/live/runtime.py"
).read_text(encoding="utf-8")


def test_ant_discovery_has_identity_readiness_gate():
    assert "def _sensor_discovery_ready" in RUNTIME
    schedule = RUNTIME.split("def _schedule_sensor_discovery", 1)[1].split(
        "def sensor_is_accepted", 1
    )[0]
    assert "if not self._sensor_discovery_ready(sensor_id):" in schedule


def test_rf_confirmed_semantic_ant_profile_can_discover_before_background_identity():
    block = RUNTIME.split("def _sensor_discovery_ready", 1)[1].split(
        "def _schedule_sensor_discovery", 1
    )[0]
    assert 'ant.metadata.get("rf_identity_confirmed")' in block
    assert "and sensor.capabilities" in block
    # Legacy/raw paths remain conservative when they did not pass the semantic
    # receiver confirmation contract.
    assert "manufacturer_id" in block
    assert "model_no" in block
    assert "catalog_product_id" in block


def test_catalog_identity_can_merge_before_ant_discovery():
    match = RUNTIME.split("def _match_sensor", 1)[1].split(
        "@staticmethod", 1
    )[0]
    assert "catalog_product_id" in match
    assert "endpoint.transport not in sensor.endpoints" in match
    assert "_merge_physical_sensors" in match


def test_provisional_merge_does_not_scan_registry():
    merge = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    assert "secondary_had_accepted_device" in merge
    assert "if secondary_had_accepted_device and not requires_reassignment:" in merge


def test_registry_cleanup_is_deferred_out_of_identity_burst():
    block = RUNTIME.split("def _schedule_merged_registry_cleanup", 1)[1].split(
        "def _cleanup_merged_registry_sensor", 1
    )[0]
    assert "await asyncio.sleep(1.0)" in block
    assert "_notify_structure_throttled()" in block


def test_radio_identity_enrichment_does_not_global_fanout():
    register = RUNTIME.split("def register_transport_sensor", 1)[1].split(
        "def register_sensor", 1
    )[0]
    assert "if is_new:" in register
    tail = register.split("if is_new:", 1)[1]
    assert "self._notify()" in tail
    assert "if structural_change:\\n            self._notify()" not in register


def test_structure_materialization_is_slow_control_plane_debounce():
    block = RUNTIME.split("def _notify_structure_throttled", 1)[1].split(
        "def suppress_entry_reload_once", 1
    )[0]
    assert "call_later(2.0" in block

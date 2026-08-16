import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ENTITIES = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
CATALOG = json.loads((ROOT / "custom_components/fitness/live/device_catalog.json").read_text())


def test_ant_acceptance_bootstraps_cached_metrics_and_fast_path_publishes_them():
    acceptance = ANT.split("def sensor_acceptance_changed", 1)[1].split("def forget_device", 1)[0]
    assert "self.receiver.devices.get(device_id)" in acceptance
    assert "self._schedule_publish_device(device, structural=True)" in acceptance

    fast_path = ANT.split("if previous_structure == structure_signature and mapped_sensor_id:", 1)[1].split(
        "sensor = self.runtime.register_transport_sensor", 1
    )[0]
    assert "if accepted:" in fast_path
    assert "self._publish_metric_values(device, mapped_sensor_id)" in fast_path


def test_dual_transport_fallback_is_data_driven_and_vendor_names_stay_in_catalog():
    rules = CATALOG.get("transport_correlation_rules") or []
    assert any(rule.get("id") == "garmin_wearable_hr_broadcast" for rule in rules)
    assert "catalog_transport_correlation" in RUNTIME
    assert "globally one-to-one" in RUNTIME
    assert "garmin" not in RUNTIME.lower()


def test_catalog_correlation_rule_requires_hr_capability_ant_identity_and_ble_family():
    rule = next(rule for rule in CATALOG["transport_correlation_rules"] if rule["id"] == "garmin_wearable_hr_broadcast")
    assert rule["capabilities"] == ["heart_rate"]
    assert rule["roles"]["antplus"]["manufacturer_id"] == 1
    assert rule["roles"]["antplus"]["profiles"] == [120]
    assert rule["roles"]["antplus"]["require_serial"] is True
    assert "Forerunner" in rule["roles"]["bluetooth"]["name_prefixes"]
    identity = (ROOT / "custom_components/fitness/live/device_identity.py").read_text()
    assert "def catalog_transport_correlation" in identity
    assert 'role.get("require_serial")' in identity


def test_last_seen_entity_exposes_one_minute_precision():
    block = ENTITIES.split("class PhysicalLastSeenSensor", 1)[1].split(
        "async def async_setup_sensor_entities", 1
    )[0]
    assert "seen.replace(second=0, microsecond=0)" in block
    assert "minute // 5" not in block


def test_training_recovery_can_reach_100_but_load_penalties_remain():
    block = MANAGER.split("# Training recovery:", 1)[1].split("# Post-exercise recovery response", 1)[0]
    assert "training_score = 100.0" in block
    assert "training_score -= 18.0" in block
    assert "training_score -= 10.0" in block
    assert "training_score -= 4.0" in block


def test_recovery_card_pairs_readiness_and_recovery_progress_as_matching_score_bars():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert 'class="recovery-score recovery-score-${kind} entity-link"' in FRONTEND
    assert 'class="recovery-score-stack"' in FRONTEND
    assert 'kind:"readiness"' in FRONTEND
    assert 'kind:"progress"' in FRONTEND
    assert "trainingRecoveryBar" not in FRONTEND
    assert 'linear-gradient(90deg,color-mix(in srgb,var(--score-tone) 38%,transparent),var(--score-tone))' in FRONTEND
    assert "training-recovery-axis" not in FRONTEND
    assert "training-recovery-marker" not in FRONTEND
    assert 'data-more-info="${_fitnessEscape(e.readiness || "")}"' in FRONTEND

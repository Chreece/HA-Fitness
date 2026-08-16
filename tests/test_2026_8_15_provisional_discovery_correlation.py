from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_catalog_correlation_can_merge_inside_discovery_before_acceptance():
    block = RUNTIME.split(
        "def _maybe_merge_correlated_dual_transport", 1
    )[1].split("def _match_sensor", 1)[0]
    assert "cohort_accepted = self.sensor_is_accepted(sensor.sensor_id)" in block
    assert "self.sensor_is_accepted(candidate.sensor_id) != cohort_accepted" in block
    assert "self.sensor_is_accepted(item.sensor_id) != cohort_accepted" in block
    assert "provisional + provisional may merge while still in Discovery" in block
    assert "accepted + provisional never merge heuristically" in block
    assert "if not self.sensor_is_accepted(sensor.sensor_id):\n            return sensor" not in block


def test_structural_observation_runs_correlation_before_discovery_is_scheduled():
    register = RUNTIME.split("def register_transport_sensor", 1)[1].split(
        "# Compatibility for older provider code/tests", 1
    )[0]
    correlation_pos = register.index("sensor = self._maybe_merge_correlated_dual_transport(sensor)")
    discovery_pos = register.index("self._schedule_sensor_discovery(sensor.sensor_id)")
    assert correlation_pos < discovery_pos
    assert "if structural_change:\n            # Strong identity matching" in register


def test_discovery_flow_identity_follows_merge_aliases():
    flow = RUNTIME.split("def _discovery_flow_matches_sensor", 1)[1].split(
        "def _sensor_discovery_ready", 1
    )[0]
    assert "self.resolve_sensor_id(provisional) == canonical" in flow
    merge = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    assert "Discovery state follows the canonical physical ID" in merge
    assert "self.endpoint_aliases[secondary.sensor_id] = primary.sensor_id" in merge

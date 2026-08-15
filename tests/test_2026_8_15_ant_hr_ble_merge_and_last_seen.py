"""Regression guards for Garmin/dual-protocol HR identity and Last seen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()


def test_last_seen_map_sensor_refreshes_on_one_minute_buckets():
    block = RUNTIME.split("def _mark_last_seen_change", 1)[1].split(
        "def _notify_profile_live_throttled", 1
    )[0]
    assert "seen.replace(second=0, microsecond=0)" in block
    assert "minute // 5" not in block


def test_ant_metric_mailbox_refreshes_endpoint_last_seen_before_values():
    block = ANT.split("def _publish_metric_values", 1)[1].split(
        "def _publish_device", 1
    )[0]
    assert "self.runtime.refresh_transport_endpoint(" in block
    assert 'getattr(device, "last_seen", None)' in block


def test_ant_structural_discovery_can_request_bounded_ble_identity_probe():
    assert "schedule_identity_probe_candidates" in ANT
    assert "Exact serial identity still decides the merge" in ANT
    assert "def schedule_identity_probe_candidates" in BT
    assert "def _async_probe_identity" in BT
    assert "manage_client_state=False" in BT


def test_ble_identity_probe_is_not_a_persistent_gatt_subscription():
    probe = BT.split("async def _async_probe_identity", 1)[1].split(
        "def sensor_connected", 1
    )[0]
    assert "await client.disconnect()" in probe
    assert "await self._subscribe" not in probe


def test_merge_keeps_meaningful_ble_name_while_ant_keeps_canonical_id():
    block = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    assert 'secondary.endpoints.get("bluetooth")' in block
    assert 'secondary_bt.metadata.get("advertised_name")' in block
    assert "primary.name = _normalize_name(secondary_bt_name)" in block

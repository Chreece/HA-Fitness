from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
ARCHIVES = (ROOT / "custom_components/fitness/device_archives.py").read_text()
BASE = (ROOT / "custom_components/fitness/device_adapters/base.py").read_text()
CYCPLUS = (ROOT / "custom_components/fitness/device_adapters/cycplus_adapter.py").read_text()
HISTORY = (ROOT / "custom_components/fitness/device_adapters/history_coordinator.py").read_text()
CYCPLUS_COORD = (ROOT / "custom_components/fitness/device_adapters/cycplus_m1.py").read_text()


def test_manual_ai_regenerate_rearms_runtime_and_fails_loudly_if_not_regenerated():
    assert "if force:\n            self._ai_runtime_disabled = False" in MANAGER
    assert '"ai_regeneration_failed"' in DASHBOARD
    assert 'after_generated_at == before_generated_at' in DASHBOARD


def test_ai_cards_show_visible_working_animation_during_regeneration():
    assert 'class="${rest?\'rest\':\'train\'} ${this._dailyLoading?\'ai-working\':\'\'}"' in FRONTEND
    assert 'class="${this._planLoading?\'ai-working\':\'\'}"' in FRONTEND
    assert "@keyframes fitnessAiPulse" in FRONTEND
    assert "ai-working-banner" in FRONTEND


def test_archive_adapters_can_opt_into_generic_remote_gatt_proxy():
    assert "remote_gatt_services: frozenset[str] = frozenset()" in BASE
    assert "def remote_gatt_services(self)" in ARCHIVES
    assert "def match_remote_gatt(" in ARCHIVES
    assert "remote_gatt_services=frozenset({CYCPLUS_M1_SERVICE_UUID})" in CYCPLUS


def test_remote_gateway_exposes_archive_services_and_gatt_rpc():
    assert '"remote_gatt_proxy": True' in REMOTE
    assert '"remote_ble_optional_services": remote_archive_services' in REMOTE
    for command in ("gatt_poll", "gatt_result", "gatt_notify"):
        assert f'fitness/remote_gateway/{command}' in REMOTE
    assert "class RemoteGattClient" in REMOTE
    assert "remote_gatt_client_for_sensor" in REMOTE
    assert 'reason="remote_gatt_connected"' in REMOTE


def test_browser_bridge_keeps_protocol_in_python_and_executes_only_gatt_ops():
    assert "async _runRemoteGattBridge(record)" in FRONTEND
    assert 'type:"fitness/remote_gateway/gatt_poll"' in FRONTEND
    assert 'type:"fitness/remote_gateway/gatt_result"' in FRONTEND
    assert 'type:"fitness/remote_gateway/gatt_notify"' in FRONTEND
    assert "await characteristic.readValue()" in FRONTEND
    assert "writeValueWithoutResponse" in FRONTEND
    assert "await characteristic.startNotifications()" in FRONTEND


def test_cycplus_and_shared_direct_history_can_use_remote_gatt_client():
    assert "remote_client = self.provider.remote_gatt_client(sensor_id)" in CYCPLUS_COORD
    assert "remote_client = self.provider.remote_gatt_client(sensor_id)" in HISTORY
    assert "await client.connect()" in CYCPLUS_COORD
    assert "await client.connect()" in HISTORY

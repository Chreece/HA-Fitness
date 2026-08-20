"""Regression contracts for restart-safe dashboards, Garmin return sync and generic remote BLE."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "fitness"
TV = (ROOT / "tv_dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
ARCHIVES = (ROOT / "device_archives.py").read_text(encoding="utf-8")
ARCHIVE_BASE = (ROOT / "device_adapters" / "base.py").read_text(encoding="utf-8")
GARMIN = (ROOT / "device_adapters" / "garmin" / "adapter.py").read_text(encoding="utf-8")


def test_multi_dashboard_definitions_survive_store_sanitization_on_restart() -> None:
    sanitize = TV[TV.index("    def _sanitize_profile"):TV.index("    def _sanitize_playlist_context")]
    assert "dashboards, active_dashboard_id = cls._sanitize_dashboards(raw)" in sanitize
    assert 'result["dashboards"] = dashboards' in sanitize
    assert 'result["active_dashboard_id"] = active_dashboard_id' in sanitize
    assert 'result["cards"] = list(active_dashboard["cards"])' in sanitize
    assert "@classmethod\n    def _sanitize_dashboards" in TV


def test_remote_web_bluetooth_picker_discovers_capabilities_after_connection() -> None:
    pair = FRONTEND[
        FRONTEND.index("  async _pairRemoteBleDevice()"):
        FRONTEND.index("  async _disconnectRemoteBleDevice", FRONTEND.index("  async _pairRemoteBleDevice()"))
    ]
    assert "acceptAllDevices:true" in pair
    assert "filters:[...FITNESS_REMOTE_BLE_SERVICES]" not in pair
    assert "const optionalServices = await this._remoteBleRequestedServices();" in pair
    assert "optionalServices," in pair

    connect = FRONTEND[
        FRONTEND.index("  async _connectRemoteBleDevice(device)"):
        FRONTEND.index("  _queueRemoteBleFrame", FRONTEND.index("  async _connectRemoteBleDevice(device)"))
    ]
    assert "for (const serviceUuid of FITNESS_REMOTE_BLE_CONNECT_SERVICES)" in connect
    assert "await server.getPrimaryService(serviceUuid)" in connect
    assert "if (!liveCharacteristicCount && !remoteArchive)" in connect
    assert "remote_ble_unsupported" in connect
    assert "service_uuids:serviceUuids" in connect
    assert "characteristic_uuids:characteristics" in connect


def test_archive_return_policy_is_generic_and_garmin_gets_immediate_reacquire() -> None:
    assert "availability_return_sync_delay: float = 3.0" in ARCHIVE_BASE
    assert "availability_return_min_gap: float = 0.0" in ARCHIVE_BASE
    assert 'getattr(adapter, "availability_return_min_gap", 0.0)' in ARCHIVES
    assert 'getattr(adapter, "availability_return_sync_delay", 3.0)' in ARCHIVES
    assert "gap >= return_min_gap" in ARCHIVES
    assert "delay=return_delay" in ARCHIVES
    assert "force=True" in ARCHIVES
    assert "availability_return_sync_delay=0.0" in GARMIN
    assert "availability_return_min_gap=60.0" in GARMIN


def test_dashboard_restart_fix_does_not_drop_spatial_card_lane_layout() -> None:
    assert 'item["x_percent"] = round(max(0.0, min(100.0, x_percent)), 1)' in TV
    assert "const rawXPercent = Number(raw.x_percent);" in FRONTEND
    assert "const targetAt = (dragRect) =>" in FRONTEND
    assert "x_percent:Math.round(Math.max(0, Math.min(100, droppedXPercent)) * 10) / 10" in FRONTEND

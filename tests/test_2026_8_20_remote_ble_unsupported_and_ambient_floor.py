from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_remote_ble_capability_failure_is_not_reported_as_transport_failure():
    pair = FRONTEND[
        FRONTEND.index("  async _pairRemoteBleDevice()"):
        FRONTEND.index("  async _disconnectRemoteBleDevice", FRONTEND.index("  async _pairRemoteBleDevice()"))
    ]
    assert 'const unsupported = detail === String(l.remote_ble_unsupported).trim();' in pair
    assert 'this._renderRemoteGatewayStatus(unsupported ? l.remote_ble_unsupported : l.remote_failed);' in pair


def test_short_dashboard_ambient_blends_through_remaining_viewport():
    assert 'this.style.setProperty("--fitness-dashboard-host-top", `${Math.round(top)}px`);' in FRONTEND
    assert 'calc(100dvh - var(--fitness-dashboard-host-top,0px))' in FRONTEND
    assert 'rgba(${r},${g},${b},${(alpha * 0.12).toFixed(4)}) 74%' in FRONTEND
    assert 'var(--primary-background-color) 100%)' in FRONTEND
    assert ':host(:not([fitness-cast-receiver]))>.fitness-ambient-layer{position:fixed!important' in FRONTEND

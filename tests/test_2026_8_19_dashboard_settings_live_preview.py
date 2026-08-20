from pathlib import Path

DASHBOARD = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()
ANT = Path("custom_components/fitness/live/antplus_core/adapter.py").read_text()


def test_ant_adapter_has_no_fake_protocol_parent_fallback():
    assert "live_adapter:antplus" not in ANT
    assert "Keep the receiver flat under ANT+" in ANT
    assert 'kwargs["via_device_id"] = None' in ANT


def test_backend_dashboard_settings_float_over_live_dashboard_preview():
    assert "Keep the dashboard visible while editing per-profile backend/dashboard settings." in DASHBOARD
    assert ".backend-flow-backdrop{background:rgba(0,0,0,.18)!important" in DASHBOARD
    assert "pointer-events:none!important" in DASHBOARD
    assert ".backend-flow-backdrop .backend-flow-modal{pointer-events:auto!important" in DASHBOARD
    assert 'if (cardPickerPreview) backdrop?.style?.setProperty("--modal-top", "4px")' in DASHBOARD
    assert 'if (backendFlowModal) backdrop?.style?.setProperty("--modal-top", "4px")' not in DASHBOARD

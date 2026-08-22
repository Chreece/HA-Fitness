from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_remote_connections_publish_local_hardware_capability():
    assert '"is_local_connection": is_local_connection' in ACCESS
    assert '"local_ha_hardware_allowed": is_local_connection' in ACCESS
    assert '"local_ha_hardware_allowed": False' in ACCESS


def test_remote_options_flow_hides_and_preserves_ha_local_light_and_cast_fields():
    for field in (
        "CONF_FEEDBACK_AREA_IDS",
        "CONF_FEEDBACK_LIGHT_IDS",
        "CONF_DASHBOARD_LIGHT_ENTITY_IDS",
        "CONF_TV_MEDIA_PLAYER_ID",
        "CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE",
    ):
        assert field in DASHBOARD
    assert "_REMOTE_LOCAL_HARDWARE_FIELDS_BY_STEP" in DASHBOARD
    assert "hidden_fields=hidden" in DASHBOARD
    assert "_preserve_remote_local_hardware_input" in DASHBOARD


def test_remote_frontend_keeps_browser_local_cast_but_hides_ha_hardware_controls():
    assert "const localHaHardwareAllowed = Boolean(this._access?.local_ha_hardware_allowed);" in FRONTEND
    assert '${localHaHardwareAllowed ? `<section class="cast-section ha-cast-section">' in FRONTEND
    assert '${localHaHardwareAllowed ? `<label class="setting-toggle"><span><strong>${_fitnessEscape(l.ignore_lights_when_cast_active)}' in FRONTEND
    assert 'localHaHardwareAllowed ? `<button class="tool cast-profile-toggle' in FRONTEND
    assert '<section class="cast-section local-cast-section">' in FRONTEND


def test_server_rejects_remote_light_feedback_and_ha_tv_operations():
    assert '"light_feedback_enabled" in msg and not access.get("local_ha_hardware_allowed")' in TV
    assert TV.count('"local_network_required"') >= 3
    assert DASHBOARD.count('"local_network_required"') >= 2
    assert 'access.get("is_admin") and access.get("local_ha_hardware_allowed")' in DASHBOARD


def test_v113_cache_contract_is_consistent():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert '"frontend_version": "unreleased-138"' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS

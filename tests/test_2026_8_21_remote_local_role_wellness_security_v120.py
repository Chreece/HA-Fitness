from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
WELLNESS = (ROOT / "custom_components/fitness/providers/wellness.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def test_role_and_network_scope_are_independent_and_remote_never_gets_local_ha_hardware():
    assert 'ROLE_ADMIN_USER = "admin_user"' in ACCOUNTS
    assert 'ROLE_USER = "user"' in ACCOUNTS
    assert 'NETWORK_LOCAL_ONLY = "local_only"' in ACCOUNTS
    assert 'NETWORK_REMOTE_ONLY = "remote_only"' in ACCOUNTS
    assert 'NETWORK_LOCAL_REMOTE = "local_remote"' in ACCOUNTS
    assert 'network_access == NETWORK_REMOTE_ONLY and not exact_remote_host' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host)' in ACCOUNTS
    assert 'is_local_connection and network_access in {NETWORK_LOCAL_ONLY, NETWORK_LOCAL_REMOTE}' in ACCESS


def test_account_ui_offers_role_then_network_scope_with_contextual_hints():
    role_at = FRONTEND.index('class="access-role-field"')
    network_at = FRONTEND.index('class="access-network-field"', role_at)
    view_at = FRONTEND.index('class="access-view-field', network_at)
    assert role_at < network_at < view_at
    assert 'option value="admin_user"' in FRONTEND
    assert 'option value="local_only"' in FRONTEND
    assert 'option value="remote_only"' in FRONTEND
    assert 'option value="local_remote"' in FRONTEND
    assert 'network_remote_only_hint' in FRONTEND


def test_nonlocal_options_cannot_enumerate_or_forge_home_assistant_sources():
    for field in (
        'CONF_WEIGHT_SCALE_ENTITY', 'CONF_LIVE_DEVICE_IDS', 'CONF_AI_ENTITY',
        'CONF_NOTIFY_ENTITY_IDS', 'CONF_TTS_ENTITY_ID', 'CONF_TTS_MEDIA_PLAYER_IDS',
        'CONF_DASHBOARD_RSS_ENTITY_IDS', 'CONF_DASHBOARD_MUSIC_ENTITY_IDS',
        'CONF_DASHBOARD_LIGHT_ENTITY_IDS', 'CONF_DASHBOARD_VIDEO_ENTITY_IDS',
        'CONF_DASHBOARD_WEATHER_ENTITY_ID',
    ):
        assert field in DASH
    assert '_REMOTE_SYSTEM_SOURCE_FIELDS_BY_STEP' in DASH
    assert '_remote_allowed_option_values' in DASH
    assert 'if str(x) in owned' in DASH
    assert '_remote_sensor_owned(sensor)' in DASH


def test_remote_dashboard_redacts_system_entity_handles_and_local_sensor_routes():
    assert '_remote_safe_metric_routes' in DASH
    assert '"entity_id", "source_entity", "owner_entity_id", "device_id"' in DASH
    assert 'if local_ha_hardware_allowed:' in DASH
    assert '_route_candidates(hass, manager) if local_ha_hardware_allowed else {}' in DASH


def test_wellness_merges_profile_owned_supported_integrations_with_direct_device_history():
    assert 'SUPPORTED_WELLNESS_DOMAINS' in WELLNESS
    assert '"garmin_connect"' in WELLNESS
    assert '"steps": frozenset' in WELLNESS
    assert 'measurement_context", "current_total"' in WELLNESS
    assert 'str(reg.device_id) not in allowed_devices' in WELLNESS
    assert 'discover_profile_wellness' in MANAGER
    assert '_async_reconcile_supported_wellness' in MANAGER
    assert 'await self._async_reconcile_supported_wellness()' in MANAGER


def test_v120_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
    assert '?v=unreleased-138' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS

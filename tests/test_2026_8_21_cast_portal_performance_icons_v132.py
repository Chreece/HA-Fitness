from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_v132_frontend_resource_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_dashcast_portal_preloads_authorized_dashboard_and_states():
    assert 'state_entity_ids: tuple[str, ...] = ()' in ACCOUNTS
    assert 'bootstrap_config: dict[str, Any] | None = None' in ACCOUNTS
    assert 'bootstrap_states: dict[str, Any] | None = None' in ACCOUNTS
    assert 'bootstrap_preferences: dict[str, Any] | None = None' in ACCOUNTS
    assert 'session.state_entity_ids = entity_ids' in ACCOUNTS
    assert 'window.__FITNESS_CAST_BOOTSTRAP__={bootstrap_payload}' in ACCOUNTS
    assert 'states:(castBootstrap.states||{{}})' in ACCOUNTS
    assert 'msg?.type==="fitness/dashboard/config"&&castBootstrap.config' in ACCOUNTS
    assert 'msg?.type==="fitness/tv/preferences"&&castBootstrap.preferences' in ACCOUNTS


def test_dashcast_state_poll_does_not_rebuild_dashboard_config_on_each_poll():
    assert 'entity_ids = set(session.state_entity_ids)' in ACCOUNTS
    assert 'if not entity_ids:' in ACCOUNTS
    assert 'setInterval(refreshStates,castPortal?2500:3000)' in ACCOUNTS
    assert 'statesRefreshInFlight' in ACCOUNTS


def test_standalone_cast_portal_has_zero_network_real_mdi_icons():
    icon_asset = (ROOT / "custom_components/fitness/frontend/fitness-mdi-icons.js").read_text(encoding="utf-8")
    assert 'window.__FITNESS_MDI_PATHS__=Object.freeze(' in icon_asset
    assert '"mdi:cast"' in icon_asset
    assert '"mdi:heart-pulse"' in icon_asset
    assert '/fitness/frontend/fitness-mdi-icons.js?v=7.4.47-fitness-1' in ACCOUNTS
    assert 'const fitnessPortalIconPath=' in ACCOUNTS
    assert 'FITNESS_MDI_SVG_BASE=' not in ACCOUNTS
    assert 'cdn.jsdelivr.net' not in ACCOUNTS
    assert '_security_headers(nonce, cast_receiver=cast_receiver)' in ACCOUNTS


def test_legacy_cast_runtime_uses_lightweight_rendering_path():
    assert 'const FITNESS_TV_CAST_LEGACY_ENGINE' in FRONTEND
    assert 'major > 0 && major < 110' in FRONTEND
    assert 'this.toggleAttribute("fitness-cast-lite", FITNESS_TV_CAST_LEGACY_ENGINE)' in FRONTEND
    assert ':host([fitness-cast-receiver]) .fitness-ambient-layer{display:none!important;filter:none!important}' in FRONTEND
    assert 'FITNESS_TV_CAST_LEGACY_ENGINE ? false : Boolean(prefs?.animations_enabled' in FRONTEND

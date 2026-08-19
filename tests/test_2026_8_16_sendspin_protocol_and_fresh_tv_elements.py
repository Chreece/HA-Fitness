from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_music_assistant_2913_uses_exact_sendspin_js_320_contract():
    assert '@sendspin/sendspin-js@3.2.0/+esm' in FRONTEND
    assert '@sendspin/sendspin-js@3.2.1/+esm' not in FRONTEND
    connect_start = FRONTEND.index("async _connectMASendspinPlayer(")
    connect_end = FRONTEND.index("async _ensureMASendspinPlayer()", connect_start)
    connect_body = FRONTEND[connect_start:connect_end]
    assert connect_body.count("await player.connect();") == 1


def test_release_specific_tv_custom_elements_bypass_stale_ha_spa_definitions():
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v75"' in FRONTEND
    assert 'FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v75"' in FRONTEND
    assert 'FITNESS_TV_LOVELACE_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card"' in FRONTEND
    assert 'FITNESS_TV_LOVELACE_SETUP_CARD_TAG = "fitness-tv-setup-card"' in FRONTEND
    assert '_fitnessDefineCustomElement(tag, FitnessTvDashboardCard)' in FRONTEND
    assert '_fitnessDefineCustomElement(tag, FitnessTvSetupCard)' in FRONTEND
    assert 'document.createElement(FITNESS_TV_DASHBOARD_CARD_TAG)' in FRONTEND
    assert 'type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`' in FRONTEND


def test_managed_lovelace_views_use_fresh_release_specific_card_types():
    assert '_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"' in DASHBOARD
    assert '_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"' in DASHBOARD
    assert '_TV_SETUP_CARD_TYPE\n            if setup or profile_wrapper' in DASHBOARD
    assert 'else _TV_DASHBOARD_CARD_TYPE' in DASHBOARD
    # Prior Fitness-owned configs remain recognizable so async_ensure_tv_dashboard
    # is allowed to migrate them rather than treating them as user content.
    assert 'card_type == "custom:fitness-tv-setup-card"' in DASHBOARD
    assert 're.fullmatch(r"custom:fitness-tv-setup-card-v\\d+", card_type)' in DASHBOARD
    assert 'card_type == "custom:fitness-tv-dashboard-card"' in DASHBOARD
    assert 're.fullmatch(r"custom:fitness-tv-dashboard-card-v\\d+", card_type)' in DASHBOARD


def test_admin_account_profile_selector_is_in_fresh_setup_class_source():
    assert 'class="access-profile-field ${role === "none" ? "hidden" : ""}"' in FRONTEND
    assert '<select data-access-profile>' in FRONTEND
    assert 'profileField?.classList.toggle("hidden", withoutProfile)' in FRONTEND
    assert 'if (profile) profile.disabled = withoutProfile' in FRONTEND


def test_revision_71_is_unique_and_uncached():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-85"' in FRONTEND
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in DASHBOARD
    assert '"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"' in DASHBOARD


def test_versioned_tv_elements_are_actually_registered():
    assert 'for (const tag of [FITNESS_TV_SETUP_CARD_TAG' in FRONTEND
    assert '_fitnessDefineCustomElement(tag, FitnessTvSetupCard)' in FRONTEND
    assert 'for (const tag of [FITNESS_TV_DASHBOARD_CARD_TAG' in FRONTEND
    assert '_fitnessDefineCustomElement(tag, FitnessTvDashboardCard)' in FRONTEND
    assert 'custom:fitness-tv-setup-card' in DASHBOARD
    assert 'custom:fitness-tv-dashboard-card' in DASHBOARD


def test_frontend_route_stays_stable_while_version_query_changes():
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in DASHBOARD
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-85"' in DASHBOARD
    assert 'FitnessDashboardResourceView(frontend_path / "fitness-dashboard.js")' in DASHBOARD
    assert 'await asyncio.to_thread(self._frontend_file.read_bytes)' in DASHBOARD

def test_dashboard_reload_reconciles_resource_and_views():
    marker = 'if domain_data.get(_SETUP_KEY):'
    block = DASHBOARD[DASHBOARD.index(marker):DASHBOARD.index('domain_data[_SETUP_KEY] = True', DASHBOARD.index(marker))]
    assert 'await _async_register_resource(hass)' in block
    assert 'await async_ensure_tv_dashboard(hass)' in block


def test_managed_tv_dashboard_migrates_all_prior_versioned_card_types():
    assert 're.fullmatch(r"custom:fitness-tv-setup-card-v\\d+", card_type)' in DASHBOARD
    assert 're.fullmatch(r"custom:fitness-tv-dashboard-card-v\\d+", card_type)' in DASHBOARD
    assert 'card_type == "custom:fitness-tv-setup-card"' in DASHBOARD
    assert 'card_type == "custom:fitness-tv-dashboard-card"' in DASHBOARD

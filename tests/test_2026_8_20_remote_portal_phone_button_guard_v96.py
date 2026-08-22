from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / 'custom_components/fitness/fitness_accounts.py').read_text()
JS = (ROOT / 'custom_components/fitness/frontend/fitness-dashboard.js').read_text()
DASH = (ROOT / 'custom_components/fitness/dashboard.py').read_text()


def test_remote_portal_allows_dynamic_shadow_styles_without_weakening_script_csp():
    assert "script-src 'self' {script}; style-src 'unsafe-inline';" in ACCOUNTS
    assert "style-src 'unsafe-inline' {script}" not in ACCOUNTS
    assert 'FITNESS_PORTAL_ICON_GLYPHS' in ACCOUNTS
    assert 'customElements.get("ha-icon")' in ACCOUNTS
    assert '--primary-background-color:#0b0f14' in ACCOUNTS


def test_every_fitness_shadow_root_gets_universal_button_overflow_guard():
    assert 'const FITNESS_BUTTON_GUARD_CSS' in JS
    assert 'overflow-wrap:anywhere!important' in JS
    assert 'white-space:normal!important' in JS
    assert 'style[data-fitness-button-guard]' in JS
    assert JS.count('_fitnessInstallButtonGuard(this)') >= 11


def test_phone_tv_toolbar_grows_and_actions_cannot_spill_over_cards():
    assert '.tv-toolbar{max-height:1600px;' in JS
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))!important' in JS
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))!important' in JS
    assert '.tv-toolbar .music-controls{grid-area:music;grid-template-columns:1fr!important' in JS
    assert '.tv-toolbar .tv-actions>.tool{width:100%;min-width:0!important;max-width:100%!important' in JS


def test_frontend_cache_revision_is_v96_everywhere():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '?v=unreleased-138' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS

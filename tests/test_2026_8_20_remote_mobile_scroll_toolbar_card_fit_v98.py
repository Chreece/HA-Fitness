from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def _method(name: str, next_name: str) -> str:
    return JS[JS.index(f"  {name}("):JS.index(f"  {next_name}(")]


def test_view_only_cards_block_actions_but_not_touch_scroll_start():
    mount = _method("_mountSelectedCards", "_motionEnabled")
    assert '["click", "dblclick", "change", "input", "submit", "contextmenu", "keydown"]' in mount
    assert '"pointerdown", "pointerup", "touchstart"' not in mount
    assert '.tv-card-slot.read-only-card{touch-action:pan-y}' in JS
    assert '.tv-card-slot.read-only-card>.tv-mounted-card{touch-action:pan-y;pointer-events:none}' in JS


def test_hidden_toolbar_has_mobile_reveal_surface_and_remote_portal_disables_pull_refresh():
    assert 'id="toolbar-reveal" class="toolbar-reveal-zone"' in JS
    assert ':host([toolbar-hidden]:not([fitness-view-only])) .toolbar-reveal-zone{display:flex}' in JS
    assert ':host([fitness-view-only]) .toolbar-reveal-zone{display:none!important}' in JS
    assert 'toolbarReveal?.addEventListener("pointerdown", revealToolbar);' in JS
    assert 'overscroll-behavior-y:none' in ACCOUNTS
    assert '--fitness-portal-top-height' in ACCOUNTS
    assert ':host([fitness-public-portal][toolbar-hidden]:not([fitness-view-only])) .toolbar-reveal-zone{position:relative;top:auto' in JS


def test_natural_cards_expand_root_card_to_its_scroll_height():
    sync = _method("_syncCardGridSpan", "_wireCardReorder")
    assert 'card.toggleAttribute("fitness-natural-height", true)' in sync
    assert 'const visualHeight = Math.max(contentVisualHeight, manualHeight > 0' in sync
    assert 'innerCard?.scrollHeight' in sync
    assert '--fitness-natural-card-min-height' in sync
    assert ':host([fitness-natural-height]) ha-card' in JS
    assert 'max-height:none!important' in JS


def test_frontend_cache_bumped_for_remote_mobile_scroll_fix():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert '?v=unreleased-110' in DASH
    assert 'frontend_version = "unreleased-110"' in ACCOUNTS

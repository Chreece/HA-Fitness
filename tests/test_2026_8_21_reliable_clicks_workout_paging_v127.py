from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'custom_components/fitness/frontend/fitness-dashboard.js').read_text()
DASH = (ROOT / 'custom_components/fitness/dashboard.py').read_text()


def test_ai_local_toggles_use_pointerdown_reliable_press_contract():
    assert 'function _fitnessBindReliablePress(element, handler)' in JS
    assert 'element.addEventListener("pointerdown"' in JS
    assert '_fitnessBindReliablePress(this.shadowRoot.querySelector(".more"),()=>this._toggleDetails())' in JS
    assert "[data-details]').forEach(b=>_fitnessBindReliablePress" in JS


def test_auto_profile_cards_defer_hass_rerender_during_pointer_gesture():
    assert 'this._fitnessPointerActive=true' in JS
    assert 'this._fitnessDeferredInteractionRender=true' in JS
    assert 'Keep the DOM stable through the following click event.' in JS


def test_workout_history_is_cursor_paginated_and_bounded():
    assert 'vol.Optional("cursor")' in DASH
    assert '"next_cursor": next_cursor' in DASH
    assert '"has_more": has_more' in DASH
    assert 'base64.urlsafe_b64encode' in DASH
    assert 'limit:this._pageSize' in JS
    assert 'this._pageSize=60' in JS
    assert 'data-load-older' in JS
    assert 'async _ensureMonthLoaded()' in JS


def test_v127_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '?v=unreleased-138' in DASH

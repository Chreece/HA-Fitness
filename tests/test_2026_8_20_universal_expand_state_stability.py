from pathlib import Path

JS = (Path(__file__).parents[1] / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_expandable_card_state_is_logical_card_scoped_not_render_scoped():
    assert "const _FITNESS_CARD_UI_STATE = new Map();" in JS
    assert "function _fitnessCardUiStateKey(element, name)" in JS
    assert "config._fitness_dashboard_id" in JS
    assert "config._fitness_card_id" in JS
    assert "function _fitnessCardUiGet(element, name, fallback)" in JS
    assert "function _fitnessCardUiSet(element, name, value)" in JS


def test_mounted_cards_receive_stable_dashboard_and_card_identity():
    assert 'card.setConfig?.({profile_entry_id:this._profile.entry_id,_fitness_dashboard_id:String(this._activeDashboardId||"main"),_fitness_card_id:String(item.id||card.localName||"card")});' in JS


def test_today_details_survive_setconfig_and_animation_is_one_shot():
    assert 'this._detailsOpen=Boolean(_fitnessCardUiGet(this,"details_open",this._detailsOpen ?? false))' in JS
    assert 'this._detailsOpen=Boolean(_fitnessCardUiSet(this,"details_open",!this._detailsOpen))' in JS
    assert 'function _fitnessCardUiConsumeChange(element, name)' in JS
    assert 'row.animatePending = false;' in JS
    assert '.ai-details[data-user-expanded="1"]{animation:aiDetailsReveal .18s ease-out both}' in JS
    assert '.ai-details{display:grid;gap:10px;margin-top:10px;animation:' not in JS


def test_other_expandable_cards_use_the_same_state_contract():
    assert 'this._showMore=Boolean(_fitnessCardUiGet(this,"show_more",this._showMore ?? false))' in JS
    assert '_fitnessCardUiSet(this,"show_more",!this._showMore)' in JS
    assert 'this._expandedDay=Number(_fitnessCardUiGet(this,"expanded_day",Number.isInteger(this._expandedDay)?this._expandedDay:-1))' in JS
    assert '_fitnessCardUiSet(this,"expanded_day",this._expandedDay===i?-1:i)' in JS
    assert '.day-details.user-expanded{animation:fitnessDetailsReveal .18s ease-out both}' in JS

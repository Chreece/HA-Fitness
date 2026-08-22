from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")


def test_tv_ai_suggestions_open_readable_structured_steps_not_raw_json():
    assert "function _fitnessWorkoutPrescriptionMarkup(workout,profile=null,hass=null)" in JS
    assert 'class="workout-step"' in JS
    assert 'class="step-badges"' in JS
    assert 'class="step-target"' in JS
    assert 'class="hero detail-toggle"' in JS
    assert 'data-details="${i}"' in JS
    assert 'this._expandedDay===i' in JS
    ai = JS[JS.index("class FitnessAiTodayCard"):JS.index("class FitnessAiLastWorkoutCard")]
    assert "JSON.stringify(device,null,2)" not in ai


def test_tv_natural_cards_measure_full_content_and_only_manual_height_cards_scroll_independently():
    assert 'Number(card.scrollHeight || 0)' in JS
    assert 'Number(innerCard?.scrollHeight || 0)' in JS
    assert '.tv-card-slot>.tv-mounted-card{border-radius:22px;--ha-card-border-radius:22px;--ha-card-border-width:0px;overflow:visible!important}' in JS
    assert ':host([fitness-cast-receiver]) ha-card.tv-shell{height:100dvh;max-height:100dvh;overflow-y:auto!important;overflow-x:hidden!important' in JS
    assert '.tv-card-slot[data-manual-height]{height:auto!important;min-height:var(--fitness-manual-card-height,120px)!important' in JS


def test_temporary_password_is_rendered_inside_its_account_row():
    assert 'const secretForAccount = Boolean(oneTimeSecret?.password)' in JS
    assert 'class="access-temp-password-field"' in JS
    assert 'data-temp-password readonly' in JS
    assert 'data-copy-temp-password' in JS
    assert 'account_id:String(account.account_id || "")' in JS
    assert 'account_id:accountId,password:String(result?.temporary_password || "")' in JS
    assert 'one-time-secret' not in JS


def test_non_remote_account_rows_hide_remote_only_fields_and_align_controls():
    assert 'access-slug-field access-remote-only' not in JS
    assert 'access-username-field' in JS
    assert 'access-url access-remote-only' in JS
    assert 'row.querySelectorAll(".access-remote-only").forEach' in JS
    assert 'grid-template-columns:repeat(2,minmax(0,1fr));gap:11px 12px;align-items:start' in JS
    assert '.access-user-head{grid-column:1/-1' in JS
    assert '.access-user-row>label{display:grid;grid-template-rows:auto minmax(44px,auto) auto' in JS
    assert '.account-enabled-head input{width:22px!important;height:22px!important' in JS
    assert '.account-remote-admin-field input{width:22px!important;height:22px!important' in JS


def test_active_native_ha_admin_remains_fitness_admin_and_sees_admin_overview():
    assert 'async def _ha_native_admin(self, connection)' in ACCESS
    native = ACCESS[ACCESS.index("async def _ha_native_admin"):ACCESS.index("async def async_descriptor")]
    assert 'getattr(user, "is_admin", False)' in native
    assert 'has_usable_admin()' not in native
    assert 'if native_admin:' in ACCESS
    assert '"is_admin": True' in ACCESS
    assert 'const isAdmin = Boolean(data?.access?.is_admin);' in JS
    assert 'if (!isAdmin) {' in JS
    assert 'cards:[{type:`custom:${FITNESS_TV_LOVELACE_SETUP_CARD_TAG}`}],' in JS

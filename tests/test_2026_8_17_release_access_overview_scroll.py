from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text(encoding="utf-8"))


def test_hassfest_lovelace_dependency_is_declared_for_alpha_release():
    assert "lovelace" in MANIFEST.get("after_dependencies", []) or "lovelace" in MANIFEST.get("dependencies", [])


def test_overview_is_admin_only_clickable_and_uses_server_cast_targets():
    assert "if (!isAdmin) {" in FRONTEND
    assert "const destination = profiles.find((profile) => profile?.access?.is_own) || profiles[0];" in FRONTEND
    assert "admin-profile-link" in FRONTEND
    assert "`/fitness-tv/profile-${entryId}`" in FRONTEND
    assert 'id="overview-cast-toggle"' in FRONTEND
    assert 'id="overview-cast-target"' in FRONTEND
    assert 'type:"fitness/tv/overview/cast"' in FRONTEND
    assert 'overview-cast-local-save' not in FRONTEND[FRONTEND.index('async _openOverviewCastPicker()'):FRONTEND.index('async _castOverviewToTarget', FRONTEND.index('async _openOverviewCastPicker()'))]
    assert 'overview-smart-tv-platform' not in FRONTEND
    assert 'overview-smart-tv-create' in FRONTEND

def test_non_admin_profiles_are_own_control_plus_explicit_view_only_only():
    assert 'principal = self._fitness_principal(connection)' in ACCESS
    assert 'visible = self._view_profile_ids(principal)' in ACCESS
    assert 'visible.add(profile_id)' in ACCESS
    assert 'return {profile_id} if profile_id and profile_id in self._all_profile_ids() else set()' in ACCESS
    assert 'if _is_admin_role(principal.get("role")):' in ACCESS
    assert 'return self._all_profile_ids()' in ACCESS

def test_last_and_live_workout_cards_have_data_and_ownership_visibility_guards():
    assert 'if (cardId === "workout") return this._profileHasLastWorkoutData(hass);' in FRONTEND
    assert 'if (cardId === "live_workout") return this._profileOwnsLiveSensor(hass);' in FRONTEND
    assert "Math.abs(number) > 1e-9" in FRONTEND
    assert 'live_sensor_metrics' in FRONTEND
    assert '"live_sensor_metrics": live_sensor_metrics' in DASHBOARD


def test_all_fitness_modals_use_one_bounded_internal_vertical_scroller():
    # The modal shell/host must never be a second scrollbar; only its designated
    # body scrolls. This especially protects the nested HA backend/options form.
    assert '#backend-flow-host{display:block;flex:1 1 auto;min-height:0;overflow:hidden!important}' in FRONTEND
    assert '#backend-flow-host{flex:1 1 auto;min-height:0;overflow-y:auto' not in FRONTEND
    assert '.backend-flow-host{display:block;flex:1 1 auto;min-height:0;overflow:hidden!important}' in FRONTEND
    assert '.flow-body{display:flex;flex-direction:column;align-items:stretch;gap:9px;padding:15px 15px max(22px,env(safe-area-inset-bottom));overflow-y:auto;overflow-x:hidden;min-height:0;flex:1 1 auto;' in FRONTEND
    assert 'scrollbar-gutter:auto' in FRONTEND
    assert 'calc(100dvh - var(--modal-top,68px) - 26px)' in FRONTEND
    assert 'max-height:calc(100dvh - 16px)' in FRONTEND


def test_text_action_rows_wrap_instead_of_clipping_the_last_lines():
    assert '.setup-actions,.profile-actions,.settings-actions,.modal-actions,.access-user-actions,.flow-actions{flex-wrap:wrap!important}' in FRONTEND
    assert '.cast-section-actions{display:flex;gap:8px;flex-wrap:wrap;min-width:0}' in FRONTEND
    assert '.remote-actions{display:flex;gap:8px;flex-wrap:wrap;min-width:0}' in FRONTEND
    assert '.flow-home{min-width:126px;max-width:min(240px,45vw);padding:7px 11px;font:inherit;white-space:normal' in FRONTEND
    assert '.tv-toolbar.fixed-profile .tv-actions{grid-area:actions;justify-content:flex-end;overflow:visible;min-width:0}' in FRONTEND

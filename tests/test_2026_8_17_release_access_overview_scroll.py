from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text(encoding="utf-8"))


def test_hassfest_lovelace_dependency_is_declared_for_alpha_release():
    assert MANIFEST["version"] == "2026.8.01a01"
    assert "lovelace" in MANIFEST.get("after_dependencies", []) or "lovelace" in MANIFEST.get("dependencies", [])


def test_overview_is_admin_only_clickable_and_supports_server_and_local_cast():
    assert "if (!isAdmin) {" in FRONTEND
    assert "const destination = profiles.find((profile) => profile?.access?.is_own) || profiles[0];" in FRONTEND
    assert "admin-profile-link" in FRONTEND
    assert "`/fitness-tv/profile-${entryId}`" in FRONTEND
    assert 'id="overview-cast-toggle"' in FRONTEND
    assert 'id="overview-cast-local"' in FRONTEND
    assert 'class="add-profile-row overview-cast-target ${unavailable ? "unavailable" : ""}"' in FRONTEND
    assert 'type:"fitness/tv/overview/cast"' in FRONTEND
    assert 'type:"fitness/tv/local_cast_credentials"' in FRONTEND
    assert "overview:true" in FRONTEND
    assert 'vol.Optional("overview", default=False)' in REMOTE
    assert "async_require_admin(connection)" in REMOTE
    assert 'view_path": "cast-overview" if overview' in REMOTE
    assert 'FITNESS_TV_OVERVIEW_LOCAL_CAST_TAB_STORAGE' in FRONTEND
    assert 'this._markOverviewLocalCast(true);' in FRONTEND
    assert 'this._overviewLocalCastSessionMarked()' in FRONTEND


def test_non_admin_profiles_are_own_control_plus_explicit_view_only_only():
    assert "visible = self._view_profile_ids(account)" in ACCESS
    assert "visible.add(profile_id)" in ACCESS
    assert "return {profile_id} if profile_id" in ACCESS
    assert "async_require_profile_control" in ACCESS
    assert 'wrapper.className = `tv-card-slot${this._canControlProfile ? "" : " read-only-card"}`' in FRONTEND
    for event in ("click", "pointerdown", "touchstart", "keydown"):
        assert f'"{event}"' in FRONTEND
    assert "event.stopImmediatePropagation()" in FRONTEND
    # Explicit view grants remain navigable without exposing the admin overview;
    # selecting a granted profile is navigation-only, while its card content stays inert.
    assert "this._openVisibleProfilesPicker();" in FRONTEND
    assert 'class="media-row visible-profile-row"' in FRONTEND
    assert 'profile?.access?.can_view !== false' in FRONTEND
    # Accounts/admin snapshot stays server-side admin protected.
    assert "async def async_admin_snapshot" in ACCESS
    assert "await self.async_require_admin(connection)" in ACCESS


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
    assert '.flow-body{display:grid;gap:9px;padding:15px;overflow-y:auto;overflow-x:hidden;min-height:0;flex:1 1 auto;' in FRONTEND
    assert 'scrollbar-gutter:stable' in FRONTEND
    assert 'calc(100dvh - var(--modal-top,68px) - 26px)' in FRONTEND
    assert 'max-height:calc(100dvh - 16px)' in FRONTEND


def test_action_rows_shrink_in_one_line_instead_of_wrapping():
    assert '.setup-actions,.profile-actions,.settings-actions,.modal-actions,.access-user-actions,.flow-actions{flex-wrap:nowrap!important;min-width:0}' in FRONTEND
    assert '.cast-section-actions{display:flex;gap:8px;flex-wrap:nowrap;min-width:0}' in FRONTEND
    assert '.remote-actions{display:flex;gap:8px;flex-wrap:nowrap;min-width:0}' in FRONTEND
    assert '.tv-toolbar.fixed-profile .tv-actions{grid-area:actions;justify-content:flex-end;overflow:visible;min-width:0}' in FRONTEND

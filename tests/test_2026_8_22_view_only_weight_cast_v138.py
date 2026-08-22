from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
SCALES = (ROOT / "custom_components/fitness/weight_scales.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
TRANS = (ROOT / "custom_components/fitness/dashboard_translations.py").read_text(encoding="utf-8")


def test_v138_frontend_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_weight_source_uses_vendor_neutral_ha_registry_evidence():
    assert "device_registry as dr, entity_registry as er" in SCALES
    assert 'platform.startswith("garmin")' not in SCALES
    assert 'composition_markers = (' in SCALES
    assert 'wearable_markers = (' in SCALES
    assert 'composition_hits >= 2 and not explicit_non_scale_device' in SCALES
    assert 'kind = "scale" if is_physical_scale else ("provider" if platform else "entity")' in SCALES
    for key in ("source_kind", "source_integration", "source_device", "source_display"):
        assert f'"{key}"' in SCALES
    assert "New weight measurement" in TRANS
    assert "Νέα μέτρηση βάρους" in TRANS
    assert 'measurement?.source_display' in JS
    assert 'sourceKind === "scale" ? "mdi:scale-bathroom" : "mdi:watch-variant"' in JS


def test_unavailable_cast_target_remains_selectable_as_saved_default():
    assert 'integration="cast"' in FLOW
    # Both profile settings surfaces retain an unavailable option and label it,
    # but do not disable that option merely because the TV is powered off.
    assert JS.count('const suffix = unavailable ? ` (${l.cast_unavailable})` : "";') >= 2
    profile_block = JS[JS.index("async _openProfileConfigure()") : JS.index("async _saveProfileConfigure(root)")]
    admin_block = JS[JS.index("async _openConfigure(profile") : JS.index("_openMusicProviderCatalog", JS.index("async _openConfigure(profile"))]
    assert '${unavailable ? "disabled" : ""}' not in profile_block
    assert '${unavailable ? "disabled" : ""}' not in admin_block
    # Saving is state-independent: only entity-domain validation is performed.
    configure = TV[TV.index("async def websocket_tv_profile_configure") : TV.index("@websocket_api.websocket_command", TV.index("async def websocket_tv_profile_configure") + 20)]
    assert 'target.startswith("media_player.")' in configure
    assert 'state == "unavailable"' not in configure


def test_remote_only_profile_does_not_get_dashboard_cast_open_action():
    assert 'localHaHardwareAllowed ? `<button class="tool" id="cast"' in JS
    assert 'localHaHardwareAllowed ? `<button class="tool" id="stop-cast"' in JS


def test_view_only_profiles_are_browsable_but_mutations_are_api_locked():
    assert ':host([fitness-view-only]) .tv-toolbar{display:grid}' in JS
    assert '.tv-card-slot.read-only-card>.tv-mounted-card{touch-action:pan-y;pointer-events:auto}' in JS
    assert "_readOnlyCardHass()" in JS
    assert 'if (prop === "callService") return async () => { throw new Error("Fitness view-only profile"); };' in JS
    for endpoint in (
        "fitness/workouts/delete",
        "fitness/workouts/edit",
        "fitness/workouts/rpe",
        "fitness/tv/preferences/save",
        "fitness/tv/dashboard/manage",
        "fitness/training/start",
    ):
        assert f'"{endpoint}"' in JS
    assert 'View-only grants may browse every dashboard' in JS
    assert 'this._activeDashboardId = dashboardId;' in JS
    assert 'if (this._canControlProfile) {' in JS
    # Workout browser/viewer remains interactive while edit/delete/RPE choices
    # are rendered only for owners/controllers.
    assert 'canControl=this._profile?.access?.can_control!==false' in JS
    assert '${canControl?`<button data-edit' in JS
    assert 'const choices = canControl ? Array.from({length:10}' in JS
    # Server endpoints remain authoritative even if a client bypasses the UI.
    for function_name in ("websocket_workouts_delete", "websocket_workouts_rpe", "websocket_workouts_edit"):
        start = DASH.index(f"async def {function_name}")
        block = DASH[start:start + 1800]
        assert "_require_fitness_options_profile_control" in block


def test_admin_cast_settings_are_removed_and_tv_rows_have_state_separator():
    picker = JS[JS.index("async _openOverviewCastPicker()") : JS.index("async _castOverviewToTarget", JS.index("async _openOverviewCastPicker()"))]
    assert "overview-cast-local-save" not in picker
    assert "overview-cast-local-mode" not in picker
    assert 'this._overviewLocalCastMode = "official";' in picker
    assert 'const suffix = state ? ` · ${state}` : "";' in picker
    prepare = JS[JS.index("async _prepareOverviewLocalCastContext()") : JS.index("async _castOverviewLocal", JS.index("async _prepareOverviewLocalCastContext()"))]
    assert "_fitnessLoadLocalCastConfig" not in prepare
    assert "const applicationId = FITNESS_TV_CAST_APP_ID" in prepare


def test_admin_ha_cast_verifies_official_then_falls_back_to_dashcast():
    start = DASH.index("async def websocket_tv_overview_cast")
    block = DASH[start:DASH.index("async def websocket_tv_overview_stop", start)]
    assert "show_lovelace_view" in block
    assert "_async_wait_overview_cast_active" in block
    assert "_async_dashcast_overview_url" in block
    assert "_async_launch_dashcast" in block
    assert "async_wait_cast_bootstrap_redeemed" in block
    assert '"transport": "home_assistant_cast"' in block
    assert '"transport": "dashcast"' in block
    assert '"connecting": False' in block
    descriptor = DASH[DASH.index("def _tv_overview_cast_descriptor") : DASH.index("def _tv_cast_targets")]
    assert 'last_seen' in descriptor
    assert '_fitness_cast_app_active(app_id)' not in descriptor
    stop = DASH[DASH.index("async def websocket_tv_overview_stop") : DASH.index("@websocket_api.websocket_command", DASH.index("async def websocket_tv_overview_stop") + 20)]
    assert "revoke_cast_sessions(target_entity_id=target)" in stop


def test_admin_smart_tv_browser_layout_and_overview_link_are_receiver_ready():
    assert 'class="cast-section smart-tv-browser-section"' in JS
    assert '.smart-tv-browser-controls{display:grid;grid-template-columns:minmax(0,1fr) auto' in JS
    assert '.smart-tv-launch-target{display:grid;grid-template-columns:minmax(120px,max-content) minmax(220px,1fr)' in JS
    assert '.smart-tv-link-row{display:grid;grid-template-columns:minmax(0,1fr) 44px' in JS
    assert 'path = f"/fitness/cast/{ticket}?fitness_cast_receiver=1"' in DASH
    assert 'overview:true' in JS

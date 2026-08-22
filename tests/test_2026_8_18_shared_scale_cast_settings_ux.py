from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONST = (ROOT / "custom_components/fitness/const.py").read_text(encoding="utf-8")
CAP = (ROOT / "custom_components/fitness/providers/capabilities.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "custom_components/fitness/weight_scales.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def _back_block() -> str:
    start = FRONTEND.index("  _handleCastRemoteBackPress(")
    end = FRONTEND.index("  _beginCastRemoteBack(", start)
    return FRONTEND[start:end]


def test_shared_scale_is_separate_from_manual_current_weight_and_shareable():
    assert 'CONF_WEIGHT_SCALE_ENTITY = "weight_scale_entity"' in CONST
    profile_fields = CAP[CAP.index("_PROFILE_ENTITY_FIELDS"):CAP.index("_PROFILE_DEVICE_FIELDS")]
    assert "    CONF_WEIGHT_SCALE_ENTITY," not in profile_fields
    assert "def weight_scale_entity_supported" in CAP
    assert "def weight_scale_entity_choices" in CAP
    assert CAP.count("enforce_ownership=False") >= 2
    assert 'custom_value=False' in FLOW[FLOW.index("def _weight_scale_selector"):FLOW.index("def _resolved_weight_default")]
    assert "weight_key: _number(20, 500, step=0.1)" in FLOW


def test_scale_router_is_event_driven_bounded_and_never_auto_attributes_weight():
    assert "async_track_state_change_event" in ROUTER
    assert "async_track_time_interval" not in ROUTER
    assert "MAX_TRACKED_SCALES = 16" in ROUTER
    assert "MAX_PENDING_MEASUREMENTS = 16" in ROUTER
    assert "STABILIZE_SECONDS = 2.5" in ROUTER
    assert "DUPLICATE_WINDOW_SECONDS" not in ROUTER
    assert 'stored.get("last_values")' in ROUTER
    process = ROUTER[ROUTER.index("async def _async_process_measurement"):ROUTER.index("def _prune_pending")]
    assert "async_accept_scale_weight" not in process
    assert "math.isfinite(value_kg)" in process
    assert "round(float(previous), 3) == rounded" in process
    assert "if len(candidates) == 1:" in process
    assert "round(float(current_weight), 3) == rounded" in process
    confirm = ROUTER[ROUTER.index("async def async_confirm"):ROUTER.index("async def async_dismiss_for_profile")]
    assert "manager.async_accept_scale_weight" in confirm
    assert "async def async_dismiss_for_profile" in ROUTER
    assert "dismissed_profile_ids" in ROUTER
    assert "async def async_accept_scale_weight" in MANAGER
    assert "permanent: bool = False" in ROUTER
    assert "if not permanent:" in ROUTER
    prune = ROUTER[ROUTER.index("def _prune_pending"):ROUTER.index("def pending_for")]
    assert "pid in self._profiles" not in prune


def test_shared_scale_confirmation_informs_users_and_admin_with_role_appropriate_choices():
    assert 'vol.Required("type"): "fitness/weight/subscribe"' in DASH
    assert 'vol.Required("type"): "fitness/weight/admin/subscribe"' in DASH
    assert 'vol.Required("type"): "fitness/weight/confirm"' in DASH
    assert 'vol.Required("type"): "fitness/weight/dismiss"' in DASH
    assert "async_control_profile_ids(connection)" in DASH
    assert 'id="weight-confirmation-host"' in FRONTEND
    prompt_start = FRONTEND.index("  _normalFitnessNotifications()")
    prompt_end = FRONTEND.index("  async _confirmWeightMeasurement", prompt_start)
    prompt = FRONTEND[prompt_start:prompt_end]
    assert "<select" not in prompt
    assert "scale_measurement_user_question" in prompt
    assert "notification_apply" in prompt
    assert "notification_ignore" in prompt
    assert "this._profile?.entry_id" in FRONTEND
    dismiss_start = FRONTEND.index("  async _dismissWeightMeasurement")
    dismiss_end = FRONTEND.index("  async _load()", dismiss_start)
    assert "profile_entry_id" in FRONTEND[dismiss_start:dismiss_end]
    assert 'type:"fitness/weight/admin/subscribe"' in FRONTEND
    admin_start = FRONTEND.index("  _updateAdminWeightMeasurementPrompt()")
    admin_end = FRONTEND.index("  async _confirmAdminWeightMeasurement", admin_start)
    admin = FRONTEND[admin_start:admin_end]
    assert '<select id="admin-weight-user">' in admin
    assert "scale_measurement_admin_question" in admin
    assert '<input type="text"' not in prompt + admin


def test_cast_double_back_is_physical_safe_and_does_not_require_matching_key_signature():
    back = _back_block()
    assert 'const physicalBack = source === "keydown" && !!event;' in back
    assert "FITNESS_TV_BACK_DISTINCT_PRESS_MS = 110" in FRONTEND
    assert "< FITNESS_TV_BACK_DISTINCT_PRESS_MS" in back
    assert "startup/system Back detected; guarded exit enabled" in back
    assert "non-physical top-level Back ignored" in back
    assert "native picker" in back
    assert "text input" in back
    assert "const signature = this._castRemoteBackSignature(event);" not in back
    assert "authorized === signature" not in back
    assert "const authorization = `physical-back:${Math.round(now)}`;" in back
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in back


def test_cast_last_selected_control_has_no_primary_blue_focus_outline():
    assert ":host([fitness-cast-receiver]) button:focus-visible" in FRONTEND
    cast_focus_start = FRONTEND.index("  _markCastRemoteFocus(")
    cast_focus_end = FRONTEND.index("  _restoreCastRemotePreviousFocus", cast_focus_start)
    cast_focus = FRONTEND[cast_focus_start:cast_focus_end]
    assert "rgba(255,255,255,.82)" in cast_focus
    assert "2px solid var(--primary-color)" not in cast_focus


def test_dashboard_settings_explain_background_application_without_new_polling_loop():
    assert 'settings_background_hint' in DASH
    assert 'settings_applying' in DASH
    assert 'settings_saved_background' in DASH
    assert 'settings_opening' in DASH
    assert 'id="flow-background-status"' in FRONTEND
    assert "_setBackgroundStatus(this._formDirty ? this._uiLabels?.settings_background_hint" in FRONTEND
    assert "_showOperationBusy(" in FRONTEND
    assert "settings_opening" in FRONTEND
    assert "settings_saved_background" in FRONTEND


def test_home_assistant_account_assignment_selector_text_is_centered():
    marker = ".profile-assign select{"
    start = FRONTEND.index(marker)
    end = FRONTEND.index("}", start)
    css = FRONTEND[start:end]
    assert "text-align:center" in css
    assert "text-align-last:center" in css
    assert "padding:0 28px" in css
    assert ".profile-assign ha-icon{position:absolute" in FRONTEND
    assert ".profile-assign select option{text-align:center}" in FRONTEND

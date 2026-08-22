from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text(encoding="utf-8")
INIT = (ROOT / "custom_components/fitness/__init__.py").read_text(encoding="utf-8")
ENTITY = (ROOT / "custom_components/fitness/entity.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_v137_frontend_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '?v=unreleased-138' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_workout_title_has_a_dedicated_non_overlapping_tools_row():
    assert 'header{display:grid;grid-template-columns:38px minmax(0,1fr)' in JS
    assert '.tools{grid-column:1/-1;display:flex' in JS
    assert '.title strong{font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' in JS


def test_workout_browser_keeps_route_evidence_and_shows_a_preview_per_row():
    assert '_route_points(data.get("gps_track")) or _route_points(extra)' in DASH
    assert 'data["has_map"] = bool(track)' in DASH
    assert '_routePreview(w)' in JS
    assert 'workout-choice-route' in JS
    assert '<polyline points="${coords}"/>' in JS


def test_option_panels_reclaim_toolbar_space_and_restore_user_policy():
    assert 'this.setAttribute("modal-focus-open", "");' in JS
    assert 'const toolbarWasHidden = Boolean(this._toolbarHidden || this.hasAttribute("toolbar-hidden"));' in JS
    assert 'if (!this._toolbarAutoHide) this._setToolbarHidden(false);' in JS
    assert 'else if (toolbarWasHidden) this._setToolbarHidden(true);' in JS


def test_menu_button_and_backend_flow_rows_cannot_stretch_vertically():
    assert '.fitness-notification-actions>button{align-self:center!important;height:auto!important' in JS
    assert '.flow-body{display:flex;flex-direction:column;align-items:stretch' in JS
    assert '.flow-actions{display:flex;justify-content:flex-end;align-items:center;align-self:stretch' in JS


def test_smart_device_picker_deduplicates_and_matches_actual_ha_discovery():
    assert 'seen_sensor_ids: set[str] = set()' in FLOW
    assert 'not runtime.sensor_discovery_visible(sensor_id)' in FLOW
    assert 'if state == "waiting" and accepted:' in FLOW
    assert 'return "configured", error' in FLOW
    assert 'def sensor_discovery_visible(self, sensor_id: str) -> bool:' in RUNTIME
    assert 'return self._discovery_flow_active(sensor_id)' in RUNTIME


def test_local_discovery_notifications_can_accept_and_assign_new_hardware():
    assert '"fitness/sensor/discovery_candidates"' in DASH
    assert '_notification_sensor_candidates(runtime, entry.entry_id)' in DASH
    assert 'if not was_accepted and not runtime.sensor_discovery_visible(sensor_id):' in DASH
    assert 'runtime.mark_sensor_accepted(sensor_id)' in DASH
    assert 'runtime.dismiss_sensor_discovery(sensor_id)' in DASH
    assert 'owner_profile_id=entry.entry_id' in DASH
    assert 'this._access?.local_ha_hardware_allowed' in JS
    assert 'type:"fitness/sensor/discovery_candidates"' in JS
    assert 'setInterval(() => void this._refreshSensorDiscoveryCandidates(), 10000)' in JS
    assert 'Pair + assign to this profile' in DASH


def test_removing_a_fitness_device_unpairs_when_safe_then_forgets_it():
    assert 'async def _async_unpair_fitness_bluetooth_device(' in INIT
    assert 'await async_bluez_remove_device(path)' in INIT
    remove_pos = INIT.index('async def async_remove_config_entry_device')
    tail = INIT[remove_pos:]
    assert tail.index('_async_unpair_fitness_bluetooth_device(') < tail.index('runtime.async_forget_sensor(')
    assert 'strict=False' in tail


def test_admin_overview_management_buttons_are_in_requested_order_and_direct_flows():
    cast = JS.index('id="overview-cast-toggle"', JS.index('class FitnessTvSetupCard'))
    accounts = JS.index('id="manage-access"', cast)
    add = JS.index('id="add-fitness-account"', accounts)
    protocols = JS.index('id="manage-fitness-protocols"', add)
    devices = JS.index('id="fitness-devices"', protocols)
    assert cast < accounts < add < protocols < devices
    assert 'this._openBackendFlow("add", "", "", "add_user")' in JS
    assert 'this._openBackendFlow("add", "", "", "manage_protocols")' in JS
    assert 'this._navigate("/config/integrations/integration/fitness")' in JS
    assert 'initialStep = ""' in JS


def test_first_install_offers_protocol_then_user_account_setup():
    assert 'menu_options=["add_protocol", "add_user"]' in FLOW


def test_existing_logical_devices_refresh_localized_wellness_name():
    assert 'def reconcile_profile_device_names(hass, entry) -> None:' in ENTITY
    assert '("evaluation", "sleep", "live", "workout", "wellness")' in ENTITY
    assert 'registry.async_update_device(device.id, name=label, model=label)' in ENTITY
    assert 'reconcile_profile_device_names(hass, entry)' in INIT

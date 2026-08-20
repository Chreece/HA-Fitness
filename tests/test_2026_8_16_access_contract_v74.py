from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_ha_admin_is_always_global_fitness_admin_independent_of_binding():
    assert 'async def _ha_native_admin(self, connection)' in ACCESS
    native = ACCESS[ACCESS.index("async def _ha_native_admin"):ACCESS.index("async def async_descriptor")]
    assert 'getattr(user, "is_admin", False)' in native
    assert 'has_usable_admin()' not in native
    require = ACCESS[ACCESS.index("async def async_require_admin"):ACCESS.index("async def async_admin_snapshot")]
    assert 'if not await self._ha_native_admin(connection):' in require
    assert 'raise Unauthorized' in require

def test_profile_ownership_and_extra_view_only_grants_are_separate():
    assert '"profile_entry_id"' in ACCESS
    assert '"view_profile_entry_ids"' in ACCESS
    assert 'principal = self._fitness_principal(connection)' in ACCESS
    assert 'visible = self._view_profile_ids(principal)' in ACCESS
    assert 'visible.add(profile_id)' in ACCESS
    assert 'return {profile_id} if profile_id and profile_id in self._all_profile_ids() else set()' in ACCESS
    assert 'async def async_profile_access' in ACCESS

def test_view_only_users_cannot_execute_profile_write_paths():
    assert 'async def _require_profile_control(' in TV
    assert TV.count('await _require_profile_control(') >= 12
    assert 'async_require_profile_control' in REMOTE
    assert 'async def _require_profile_access(' in TV


def test_dashboard_config_only_returns_profiles_current_user_may_see():
    assert 'visible_profile_ids = await access_controller.async_visible_profile_ids(' in DASH
    assert 'control_profile_ids = await access_controller.async_control_profile_ids(' in DASH
    assert 'if entry.entry_id not in visible_profile_ids:' in DASH
    assert '"can_control": entry.entry_id in control_profile_ids' in DASH
    assert '_tv_cast_targets(hass, registry) if access.get("is_admin") else []' in DASH


def test_unauthorized_and_view_only_pages_have_explicit_ui_and_no_control_tools():
    assert "denied:labels.access_denied" in JS
    assert "denied_hint:labels.access_denied_hint" in JS
    assert "view_only:labels.view_only" in JS
    assert "view_only_hint:labels.view_only_hint" in JS
    assert 'denied:"Access denied"' not in JS
    assert 'if (this._accessDenied)' in JS
    assert 'const canControl = Boolean(this._access?.is_admin || this._profile?.access?.can_control);' in JS
    assert ': (canControl ? [' in JS
    assert 'class="tool backend-tool"' in JS
    assert 'class="tool configure-tool"' in JS
    assert ': "");' in JS
    assert 'const musicTools = canControl ?' in JS
    assert 'id="play"' in JS


def test_access_admin_can_assign_owner_and_additional_view_only_profiles():
    assert 'class="access-profile-field"' in JS
    assert 'data-account-profile' in JS
    assert 'data-account-view' in JS
    assert 'view_profile_entry_ids:[...row.querySelectorAll("[data-account-view]:checked")]' in JS
    assert 'vol.Optional("view_profile_entry_ids", default=[])' in ACCOUNTS
    assert 'role === "admin" ? ""' in JS

def test_lovelace_uses_stable_card_contract_and_current_module_registers_aliases():
    assert '_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"' in DASH
    assert '_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"' in DASH
    assert 'FITNESS_TV_LOVELACE_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card"' in JS
    assert 'FITNESS_TV_LOVELACE_SETUP_CARD_TAG = "fitness-tv-setup-card"' in JS
    assert '"fitness-tv-setup-card-v73"' in JS
    assert '"fitness-tv-dashboard-card-v73"' in JS


def test_frontend_server_version_contract_can_force_reload_after_future_update():
    assert '"frontend_version": "unreleased-110"' in DASH
    assert '_fitnessEnsureFrontendVersion' in JS
    assert 'location.reload();' in JS


def test_owned_profile_backend_options_flow_uses_fitness_authorized_websocket_proxy():
    assert '"fitness/dashboard/options_flow/start"' in DASH
    assert '"fitness/dashboard/options_flow/step"' in DASH
    assert '"fitness/dashboard/options_flow/cancel"' in DASH
    assert '_require_fitness_options_profile_control' in DASH
    assert 'async_require_profile_control' in DASH
    assert '_fitness_options_flow_matches_profile' in DASH
    assert 'hass.config_entries.options.async_init(entry.entry_id)' in DASH
    assert 'hass.config_entries.options.async_configure' in DASH
    assert 'hass.config_entries.options.async_abort' in DASH
    assert 'voluptuous_serialize.convert' in DASH
    assert 'custom_serializer=cv.custom_serializer' in DASH


def test_normal_profile_options_ui_does_not_use_home_assistant_admin_only_options_rest_api():
    options_start = JS.index('this._fitnessOptionsFlow = mode !== "add";')
    options_end = JS.index('await this._renderFlow();', options_start)
    options_block = JS[options_start:options_end]
    assert 'fitness/dashboard/options_flow/start' in options_block
    assert 'config/config_entries/options/flow' not in options_block
    assert 'type:"fitness/dashboard/options_flow/step"' in JS
    assert 'type:"fitness/dashboard/options_flow/cancel"' in JS

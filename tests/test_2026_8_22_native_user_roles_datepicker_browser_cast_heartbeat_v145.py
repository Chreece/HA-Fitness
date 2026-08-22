from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")
ACCOUNTS = (FIT / "fitness_accounts.py").read_text(encoding="utf-8")
DASH = (FIT / "dashboard.py").read_text(encoding="utf-8")
INIT = (FIT / "__init__.py").read_text(encoding="utf-8")
FRONT = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
TV = (FIT / "tv_dashboard.py").read_text(encoding="utf-8")


def test_native_add_service_starts_with_protocol_or_user_choice_then_admin_access():
    assert 'menu_options=["add_protocol", "add_user"]' in FLOW
    assert "async def async_step_add_protocol" in FLOW
    assert "async def async_step_add_user" in FLOW
    assert "return await self.async_step_account_access()" in FLOW
    assert "async def async_step_account_access" in FLOW
    assert "async def async_step_account_credentials" in FLOW
    assert 'self.context.get("fitness_dashboard_flow")' in FLOW


def test_dashboard_add_user_role_prelude_is_creation_only_and_admin_gated():
    assert 'this._mode === "add" && this._initialStep === "add_user"' in FRONT
    assert 'this._mode === "options" || this._initialStep === "add_user"' not in FRONT
    assert 'type:"fitness/dashboard/config_flow/start"' in FRONT
    assert 'network_access:String(this._pendingAccountAccess?.network_access || "") || undefined' in FRONT
    assert 'vol.Optional("network_access"): vol.In({"local_only", "remote_only", "local_remote"})' in DASH
    assert 'context = {"source": "user", "fitness_dashboard_flow": True}' in DASH
    assert 'context["fitness_network_access"] = network_access' in DASH
    assert "await _require_fitness_config_flow_admin(hass, connection)" in DASH


def test_birthday_uses_native_date_selector_with_year_in_create_and_edit():
    assert 'vol.Required(CONF_DATE_OF_BIRTH, default="1980-01-01"): selector.DateSelector()' in FLOW
    assert 'CONF_DATE_OF_BIRTH, default=dob.isoformat()' in FLOW
    assert FLOW.count('selector.DateSelector()') >= 4
    create = FLOW[FLOW.index("async def async_step_user"):FLOW.index("async def async_step_required")]
    edit = FLOW[FLOW.index("async def async_step_profile"):FLOW.index("async def async_step_fitness_inputs")]
    for block in (create, edit):
        assert "CONF_BIRTH_DAY" not in block
        assert "CONF_BIRTH_MONTH" not in block
        assert "CONF_BIRTH_YEAR" not in block


def test_remote_only_new_and_existing_profiles_hide_local_ha_controls():
    assert "def _remote_only_profile_setup" in FLOW
    create_feedback = FLOW[FLOW.index("async def async_step_feedback"):FLOW.index("async def async_step_tv_dashboard")]
    assert "if not self._remote_only_profile_setup():" in create_feedback
    create_tv = FLOW[FLOW.index("async def async_step_tv_dashboard"):FLOW.index("async_get_options_flow")]
    assert "if not self._remote_only_profile_setup():" in create_tv
    assert "async def _remote_only_account" in FLOW
    options = FLOW[FLOW.index("class FitnessOptionsFlow"):]
    assert 'account = controller.account_by_profile(self.config_entry.entry_id)' in options
    assert options.count("remote_only = await self._remote_only_account()") >= 2
    assert "def account_by_profile" in ACCOUNTS


def test_native_profile_account_bootstrap_never_persists_plaintext_password():
    assert '_PENDING_ACCOUNT_KEY = "_pending_fitness_account"' in FLOW
    assert "async_prepare_initial_password" in FLOW
    assert 'self._native_temporary_password = ""' in FLOW
    assert "async def async_prepare_initial_password" in ACCOUNTS
    assert "async def async_finalize_pending_profile_account" in ACCOUNTS
    assert 'entry.data.get("_pending_fitness_account")' in INIT
    assert 'data.pop("_pending_fitness_account", None)' in INIT
    assert INIT.index("await async_setup_dashboard(hass)") < INIT.index('entry.data.get("_pending_fitness_account")')


def test_browser_tv_portal_owns_a_heartbeat_lease_until_it_goes_stale():
    assert "CAST_CLIENT_STALE_SECONDS = 14.0" in TV
    assert "cast_cutoff = current - CAST_CLIENT_STALE_SECONDS" in TV
    assert 'cutoff = cast_cutoff if bool(meta.get("is_cast_receiver")) else browser_cutoff' in TV
    assert "portalHeartbeatTimer=setInterval" in ACCOUNTS
    assert "if(castPortal)portalHeartbeatTimer=setInterval" in ACCOUNTS
    assert "4000" in ACCOUNTS
    assert 'type:"fitness/tv/heartbeat"' in ACCOUNTS
    assert "is_cast_receiver:true" in ACCOUNTS
    assert "result?.stop_requested||result?.cast_conflict" in ACCOUNTS


def test_stale_browser_tv_after_ha_restart_self_terminates_instead_of_auth_retrying():
    assert '"error": "cast_session_expired"' in ACCOUNTS
    assert "raise web.HTTPGone(" in ACCOUNTS
    assert "const expireCastPortal=(status,data={{}})=>" in ACCOUNTS
    assert "[401,403,404,410].includes" not in ACCOUNTS
    assert "Number(status||0)===410" in ACCOUNTS
    assert "clearInterval(portalHeartbeatTimer)" in ACCOUNTS
    assert 'location?.replace?.("about:blank")' in ACCOUNTS


def test_v145_frontend_cache_bust_reaches_ha_and_restricted_tv_portal():
    assert "cast-ui-155" in DASH
    assert "cast-ui-155" in ACCOUNTS

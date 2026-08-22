from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
FIT = (ROOT / "custom_components/fitness/device_adapters/garmin/fit.py").read_text(encoding="utf-8")
GARMIN = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text(encoding="utf-8")


def test_fitness_accounts_are_independent_private_credentials_not_ha_user_bindings():
    assert 'ACCOUNT_STORE_KEY = "fitness.accounts"' in ACCOUNTS
    assert 'private=True' in ACCOUNTS
    assert 'hashlib.scrypt(' in ACCOUNTS
    assert 'hmac.compare_digest(actual, expected)' in ACCOUNTS
    assert '"legacy_ha_user_id"' in ACCOUNTS  # migration marker only
    assert 'vol.Required("type"): "fitness/accounts/save"' in ACCOUNTS
    registration = ACCESS[ACCESS.index("def async_register_fitness_access_websocket_commands"):]
    assert 'async_register_command(hass, websocket_fitness_access_account_save)' not in registration
    assert 'async_register_command(hass, websocket_fitness_external_access_save)' not in registration


def test_native_ha_admin_remains_global_fitness_admin_alongside_independent_admins():
    assert 'async def _ha_native_admin(self, connection)' in ACCESS
    native = ACCESS[ACCESS.index("async def _ha_native_admin"):ACCESS.index("async def async_descriptor")]
    assert 'getattr(user, "is_active", True)' in native
    assert 'getattr(user, "is_admin", False)' in native
    assert 'has_usable_admin()' not in native
    require = ACCESS[ACCESS.index("async def async_require_admin"):ACCESS.index("async def async_admin_snapshot")]
    assert 'if not await self._ha_native_admin(connection):' in require
    assert 'raise Unauthorized' in require


def test_roles_acl_and_view_only_tv_have_expected_security_boundaries():
    assert 'ROLE_ADMIN = "admin"' in ACCOUNTS
    assert 'ROLE_ADMIN_USER = "admin_user"' in ACCOUNTS
    assert 'ROLE_USER = "user"' in ACCOUNTS
    assert 'NETWORK_LOCAL_ONLY = "local_only"' in ACCOUNTS
    assert 'NETWORK_REMOTE_ONLY = "remote_only"' in ACCOUNTS
    assert 'NETWORK_LOCAL_REMOTE = "local_remote"' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_ONLY and not local_client' in ACCOUNTS
    assert 'network_access == NETWORK_REMOTE_ONLY and not exact_remote_host' in ACCOUNTS
    assert 'remote_host_mismatch' in ACCOUNTS
    assert 'return {profile_id} if profile_id' in ACCESS
    assert ':host([fitness-view-only]) .tv-toolbar{display:grid}' in JS
    assert '_readOnlyCardHass()' in JS
    assert 'Fitness view-only profile' in JS
    assert 'view_profile_entry_ids' in ACCESS

def test_remote_login_is_secure_browser_session_and_public_hostname_is_confined():
    login = ACCOUNTS[ACCOUNTS.index("class FitnessPortalLoginView"):ACCOUNTS.index("class FitnessPortalPasswordView")]
    session_cookie = login[login.index("response.set_cookie(\n            _SESSION_COOKIE"):login.index("response.del_cookie(_LOGIN_CSRF_COOKIE")]
    assert 'secure=True' in session_cookie
    assert 'httponly=True' in session_cookie
    assert 'samesite="Strict"' in session_cookie
    assert 'max_age=' not in session_cookie
    assert '_LANGUAGE_COOKIE, session.language' in login
    assert 'max_age=31536000' in login
    assert '_SESSION_MAX_AGE = timedelta(hours=12)' in ACCOUNTS
    assert '_SESSION_IDLE_MAX = timedelta(hours=2)' in ACCOUNTS
    assert 'X-Fitness-CSRF' in ACCOUNTS
    assert 'Content-Security-Policy' in ACCOUNTS
    assert 'Strict-Transport-Security' in ACCOUNTS
    router = ACCOUNTS[ACCOUNTS.index("def async_register_fitness_portal_routing"):]
    assert 'allowed_prefixes = ("/fitness-auth/", "/fitness/frontend/", "/fitness/brand/")' in router
    assert 'raise web.HTTPNotFound(text="This hostname serves the restricted HA-Fitness portal only")' in router


def test_password_policy_and_first_login_are_strong_and_one_time_secret_is_admin_only():
    assert 'if len(value) < 14:' in ACCOUNTS
    assert 'password_too_predictable' in ACCOUNTS
    assert 'password_too_repetitive' in ACCOUNTS
    assert 'password_contains_account_info' in ACCOUNTS
    assert 'password_change_required' in ACCOUNTS
    assert '_TEMP_ALPHABET' in ACCOUNTS
    assert 'classes = (' in ACCOUNTS
    assert 'rng = secrets.SystemRandom()' in ACCOUNTS
    assert 'rng.shuffle(chars)' in ACCOUNTS
    assert 'for _attempt in range(32):' in ACCOUNTS
    assert 'secrets.choice(_TEMP_ALPHABET)' in ACCOUNTS
    assert '"temporary_password": temporary_password' in ACCOUNTS
    assert 'The plaintext is returned only in this response and is never saved.' in ACCOUNTS


def test_remote_account_diagnostics_are_visible_and_live_refresh_without_replacing_edits():
    for token in (
        '"active_sessions"', '"last_login_at"', '"last_seen_at"', '"last_error_code"',
        '"failed_login_count"', '"lockout_until"', '"dns_state"', '"login_scope"',
    ):
        assert token in ACCOUNTS
    assert 'class="account-diagnostics"' in JS
    assert 'data-account-state' in JS
    assert 'data-diag="sessions"' in JS
    assert 'data-diag="dns"' in JS
    assert 'this._fitnessAccountDiagnosticsTimer = setInterval' in JS
    assert '8000' in JS


def test_remote_subdomain_is_account_owned_and_admin_portal_can_manage_accounts():
    assert 'remote_slug' in ACCOUNTS
    assert 'remote_url = f"https://{slug}.{base}"' in ACCOUNTS
    assert 'account_by_remote_host' in ACCOUNTS
    assert 'data-account-slug' in JS
    assert 'data-account-url' in JS
    assert 'const ADMIN_VIEW="__fitness_admin__"' in ACCOUNTS
    assert 'document.createElement("fitness-tv-setup-card")' in ACCOUNTS
    assert 'type:"fitness/accounts/admin"' in JS


def test_remote_account_persists_when_cloudflare_is_down_and_settings_save_retries_dns():
    assert "cloudflare_publish:{getattr(err, 'code', err)}" in ACCOUNTS
    publish_block = ACCOUNTS[ACCOUNTS.index('if should_publish:'):ACCOUNTS.index('self._revoke_account_sessions(account_id)', ACCOUNTS.index('if should_publish:'))]
    assert 'raise ValueError("cloudflare_publish_failed")' not in publish_block
    settings = ACCESS[ACCESS.index('async def websocket_fitness_access_settings_save'):ACCESS.index('@websocket_api.websocket_command({', ACCESS.index('async def websocket_fitness_access_settings_save'))]
    assert 'async_reconcile_remote_dns()' in settings


def test_garmin_decoder_reprocesses_unsupported_local_archive_and_preserves_unknown_named_data():
    assert 'GARMIN_PAYLOAD_DECODER_REVISION = 3' in GARMIN
    assert 'if kind == "unsupported":' in GARMIN
    assert 'int(cached.get("decoder_revision") or 0) < GARMIN_PAYLOAD_DECODER_REVISION' in GARMIN
    assert 'generic_wellness_from_fit(' in GARMIN
    assert 'record["fit_inventory"] = inventory' in GARMIN
    assert '"samples": sample_values' in FIT
    for metric in (
        '"steps"', '"stress"', '"respiratory_rate"', '"spo2"', '"resting_heart_rate"',
        '"body_battery"', '"moderate_minutes"', '"vigorous_minutes"', '"sleep_score"',
        '"systolic_blood_pressure"', '"diastolic_blood_pressure"', '"vo2_max"',
    ):
        assert metric in FIT
    assert 'field_name.startswith("unknown_") or field_name.isdigit()' in FIT


def test_ai_training_suggestion_has_clickable_detail_reveal():
    assert 'more_details:"More details"' in JS
    assert 'less_details:"Less details"' in JS
    assert 'aria-controls="ai-plan-details"' in JS
    assert 'class="ai-details"' in JS
    assert 'structured_workout' in JS
    assert 'why_this' in JS


def test_v92_cache_contract():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '?v=unreleased-138' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS

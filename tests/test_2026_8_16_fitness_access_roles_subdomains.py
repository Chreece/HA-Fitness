from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DOC = (ROOT / "docs/REMOTE_ACCESS.md").read_text()


def test_fitness_access_roles_are_persistent_admin_assigned_and_owner_bootstrapped():
    assert 'ROLE_ADMIN = "admin"' in ACCOUNTS
    assert 'ROLE_ADMIN_USER = "admin_user"' in ACCOUNTS
    assert 'ROLE_USER = "user"' in ACCOUNTS
    assert 'NETWORK_LOCAL_ONLY = "local_only"' in ACCOUNTS
    assert 'NETWORK_REMOTE_ONLY = "remote_only"' in ACCOUNTS
    assert 'NETWORK_LOCAL_REMOTE = "local_remote"' in ACCOUNTS
    assert 'ACCOUNT_STORE_KEY = "fitness.accounts"' in ACCOUNTS
    assert 'private=True' in ACCOUNTS
    assert 'vol.Required("type"): "fitness/accounts/save"' in ACCOUNTS
    assert 'vol.Required("type"): "fitness/accounts/delete"' in ACCOUNTS
    assert 'vol.Required("type"): "fitness/access/profile/delete"' in ACCESS
    registration = ACCESS[ACCESS.index('def async_register_fitness_access_websocket_commands'):]
    assert 'async_register_command(hass, websocket_fitness_access_account_save)' not in registration
    assert 'async def _ha_native_admin(self, connection)' in ACCESS
    assert 'getattr(user, "is_admin", False)' in ACCESS

def test_local_and_remote_sessions_are_enforced_server_side():
    assert 'network_access == NETWORK_LOCAL_ONLY and not local_client' in ACCOUNTS
    assert 'network_access == NETWORK_REMOTE_ONLY and not exact_remote_host' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host)' in ACCOUNTS
    assert 'remote_host_mismatch' in ACCOUNTS
    assert 'principal = self._fitness_principal(connection)' in ACCESS
    assert 'visible = self._view_profile_ids(principal)' in ACCESS
    assert 'visible.add(profile_id)' in ACCESS
    assert 'return {profile_id} if profile_id and profile_id in self._all_profile_ids() else set()' in ACCESS
    assert 'raise Unauthorized' in ACCESS

def test_remote_accounts_use_unique_logical_subdomains_and_direct_profile_urls():
    assert 'remote_slug' in ACCOUNTS
    assert 'raise ValueError("username_in_use")' in ACCOUNTS
    assert '"remote_slug": slug' in ACCOUNTS
    assert 'remote_url = f"https://{slug}.{base}"' in ACCOUNTS
    assert 'account_by_remote_host' in ACCOUNTS
    assert 'Cloudflare' in ACCESS
    assert 'DNS-only A record' in DOC
    assert 'Remote Fitness account' in DOC or 'remote Fitness account' in DOC

def test_dashboard_never_enumerates_other_profiles_for_normal_users():
    assert 'visible_profile_ids = await access_controller.async_visible_profile_ids(' in DASH
    assert 'if entry.entry_id not in visible_profile_ids:' in DASH
    assert '"access": access' in DASH
    assert 'access.get("is_admin") and access.get("local_ha_hardware_allowed")' in DASH


def test_profile_scoped_tv_and_remote_gateway_commands_require_access():
    assert 'async def _require_profile_access(' in TV
    assert TV.count('await _require_profile_control(') >= 12
    for command in (
        'fitness/tv/preferences',
        'fitness/tv/media_command',
        'fitness/tv/music/search',
        'fitness/tv/start_workout',
        'fitness/tv/ack',
    ):
        assert command in TV
    assert 'async def _require_profile_access(' in REMOTE
    assert 'async_require_profile_control' in REMOTE
    assert REMOTE.count('await _require_profile_access(') >= 6
    for command in (
        'fitness/remote_gateway/hello',
        'fitness/remote_gateway/ble_frames',
        'fitness/remote_gateway/ant_packets',
        'fitness/remote_gateway/status',
        'fitness/tv/local_cast_credentials',
    ):
        assert command in REMOTE


def test_fitness_accounts_ui_is_admin_only_and_users_cannot_self_enroll():
    assert 'this._access = data?.access' in JS
    assert 'this._access?.is_admin' in JS
    assert 'id="manage-access"' in JS
    assert 'async _openAccessAdmin()' in JS
    assert '_renderAccessAdmin(snapshot || {})' in JS
    assert 'type:"fitness/accounts/admin"' in JS
    assert 'type:"fitness/accounts/save"' in JS
    assert 'type:"fitness/accounts/delete"' in JS
    assert 'type:"fitness/accounts/reset_password"' in JS
    assert 'type:"fitness/access/profile/delete"' in JS
    assert 'id="access-base-domain"' in JS
    assert 'href="/config/person"' not in JS

def test_profile_identity_is_sent_for_tts_and_remote_gateway_status():
    assert 'type:"fitness/tv/ack",' in JS
    assert 'profile_entry_id:this._profile?.entry_id' in JS
    status_blocks = [part for part in JS.split('type:"fitness/remote_gateway/status"')[1:]]
    assert status_blocks
    assert all('profile_entry_id:this._profile?.entry_id' in part[:220] for part in status_blocks)


def test_removed_account_is_forced_out_of_an_already_open_profile():
    assert '_isFitnessAccessDenied(err)' in JS
    assert '_handleFitnessAccessDenied()' in JS
    assert 'history.replaceState(null, "", "/fitness-tv/main")' in JS
    heartbeat = JS[JS.index('  async _heartbeat() {'):JS.index('  async _sendMediaCommand', JS.index('  async _heartbeat() {'))]
    assert 'this._isFitnessAccessDenied(err)' in heartbeat
    assert 'this._handleFitnessAccessDenied()' in heartbeat


def test_access_release_bumps_one_frontend_cache_revision():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '?v=unreleased-138' in DASH


def test_fitness_admin_can_keep_an_own_profile_and_ha_user_link_is_current():
    assert 'ROLE_ADMIN_USER = "admin_user"' in ACCOUNTS
    assert 'if _role_requires_profile(role) and not profile_id:' in ACCOUNTS
    assert 'if role == ROLE_ADMIN and profile_id:' in ACCOUNTS
    assert 'views.clear()' in ACCOUNTS
    assert 'data-account-profile' in JS
    assert 'role_admin_user' in JS
    assert 'href="/config/person"' not in JS
    assert 'legacy_ha_user_id' in ACCOUNTS
    assert 'Credentials cannot be migrated because the old model delegated passwords' in ACCOUNTS


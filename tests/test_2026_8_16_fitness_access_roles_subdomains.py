from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DOC = (ROOT / "docs/REMOTE_ACCESS.md").read_text()


def test_fitness_access_roles_are_persistent_admin_assigned_and_owner_bootstrapped():
    assert 'ROLE_ADMIN = "admin"' in ACCESS
    assert 'ROLE_LOCAL = "local"' in ACCESS
    assert 'ROLE_REMOTE = "remote"' in ACCESS
    assert 'ACCESS_STORE_KEY = "fitness.access_control"' in ACCESS
    assert "await self.hass.auth.async_get_owner()" in ACCESS
    assert 'getattr(user, "is_admin", False)' in ACCESS
    assert '"can_manage": True' in ACCESS
    assert 'vol.Required("type"): "fitness/access/account/save"' in ACCESS
    assert 'vol.Required("type"): "fitness/access/account/delete"' in ACCESS
    assert 'vol.Required("type"): "fitness/access/profile/delete"' in ACCESS


def test_local_and_remote_sessions_are_enforced_server_side():
    assert 'if role == ROLE_LOCAL:' in ACCESS
    assert '_is_local_remote(getattr(connection, "remote", None))' in ACCESS
    assert 'if role == ROLE_REMOTE:' in ACCESS
    assert 'self._refresh_token_client_host(connection) == expected' in ACCESS
    assert 'getattr(connection, "refresh_token_id", None)' in ACCESS
    assert 'self.hass.auth.async_get_refresh_token' in ACCESS
    assert 'visible = self._view_profile_ids(account)' in ACCESS
    assert 'visible.add(profile_id)' in ACCESS
    assert 'raise Unauthorized' in ACCESS
    assert '"is_admin": False' in ACCESS
    assert 'getattr(user, "is_admin", False)' in ACCESS


def test_remote_accounts_use_unique_logical_subdomains_and_direct_profile_urls():
    assert 'remote_base_domain' in ACCESS
    assert 'remote_slug' in ACCESS
    assert '_default_remote_slug' in ACCESS
    assert 'raise ValueError("remote_slug_in_use")' in ACCESS
    assert 'f"https://{expected_host}/fitness-tv/profile-{account.get(\'profile_entry_id\')}"' in ACCESS
    assert "wildcard-DNS model" in ACCESS
    assert "wildcard dns" in DOC.lower()
    assert "Removing the Fitness account immediately removes its binding" in DOC


def test_dashboard_never_enumerates_other_profiles_for_normal_users():
    assert 'visible_profile_ids = await access_controller.async_visible_profile_ids(' in DASH
    assert 'if entry.entry_id not in visible_profile_ids:' in DASH
    assert '"access": access' in DASH
    assert '_tv_cast_targets(hass, registry) if access.get("is_admin") else []' in DASH


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
    assert '_renderAccessAdmin(snapshot)' in JS
    assert 'type:"fitness/access/admin"' in JS
    assert 'type:"fitness/access/account/save"' in JS
    assert 'type:"fitness/access/account/delete"' in JS
    assert 'type:"fitness/access/profile/delete"' not in JS
    assert 'data-profile-entry' not in JS
    assert 'id="access-base-domain"' in JS
    assert 'href="/config/person"' in JS


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
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in JS
    assert '?v=unreleased-82' in DASH


def test_fitness_admin_can_keep_an_own_profile_and_ha_user_link_is_current():
    assert 'existing.get("role") in {ROLE_ADMIN, ROLE_LOCAL, ROLE_REMOTE}' in ACCESS
    assert 'role == ROLE_ADMIN' in ACCESS
    assert 'requested_profile_id' in ACCESS
    assert 'row["profile_entry_id"] = requested_profile_id' in ACCESS
    assert 'profileField?.classList.toggle("hidden", withoutProfile);' in JS
    assert 'if (profile) profile.disabled = withoutProfile;' in JS
    assert '.access-role-field,.access-profile-field,.access-language-field{display:block;min-width:0;align-self:stretch}' in JS
    assert 'href="/config/person"' in JS
    assert 'runtime_available": False' in DASH

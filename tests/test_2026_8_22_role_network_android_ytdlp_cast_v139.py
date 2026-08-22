from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
SCALES = (ROOT / "custom_components/fitness/weight_scales.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")
TRANS = (ROOT / "custom_components/fitness/dashboard_translations.py").read_text(encoding="utf-8")


def test_v139_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_roles_and_network_access_are_independent_with_legacy_migration():
    for marker in (
        'ROLE_ADMIN = "admin"',
        'ROLE_ADMIN_USER = "admin_user"',
        'ROLE_USER = "user"',
        'NETWORK_LOCAL_ONLY = "local_only"',
        'NETWORK_REMOTE_ONLY = "remote_only"',
        'NETWORK_LOCAL_REMOTE = "local_remote"',
    ):
        assert marker in ACCOUNTS
    assert 'if raw_role == _LEGACY_ROLE_LOCAL:' in ACCOUNTS
    assert 'return ROLE_USER, NETWORK_LOCAL_ONLY' in ACCOUNTS
    assert 'return ROLE_USER, NETWORK_REMOTE_ONLY' in ACCOUNTS
    assert 'return ROLE_USER, NETWORK_LOCAL_REMOTE' in ACCOUNTS
    assert 'if raw_role == ROLE_ADMIN and profile_entry_id:' in ACCOUNTS
    assert 'raw_role = ROLE_ADMIN_USER' in ACCOUNTS


def test_admin_account_flow_is_admin_only_and_users_can_only_share_own_dashboard():
    save = ACCOUNTS[ACCOUNTS.index('async def websocket_fitness_accounts_save'):]
    assert 'await _require_fitness_admin(hass, connection)' in save[:500]
    assert 'fitness/accounts/share/save' in ACCOUNTS
    share = ACCOUNTS[ACCOUNTS.index('async def websocket_fitness_accounts_share_save'):ACCOUNTS.index('@websocket_api.websocket_command', ACCOUNTS.index('async def websocket_fitness_accounts_share_save') + 20)]
    assert '_sharing_owner_account_id' in share
    assert 'async_set_shared_viewers' in share
    assert 'role' not in share
    assert 'network_access' not in share
    assert '"fitness/accounts/share/save"' in JS[JS.index('_readOnlyCardHass()'):JS.index('_mountSelectedCards()', JS.index('_readOnlyCardHass()'))]


def test_account_ui_orders_role_network_and_view_grants_and_conditions_later_options():
    role = JS.index('class="access-role-field"')
    network = JS.index('class="access-network-field"', role)
    views = JS.index('class="access-view-field', network)
    assert role < network < views
    assert 'currentRole === "admin"' in JS
    assert 'currentRole !== "user"' in JS
    assert 'currentNetwork === "remote_only"' in JS
    assert 'const remoteActive = currentNetwork !== "local_only"' in JS
    for key in ('role_admin_user', 'network_access', 'network_local_only', 'network_remote_only', 'network_local_remote', 'view_rights_accounts'):
        assert f'"{key}"' in TRANS


def test_network_scope_is_enforced_server_side_for_login_and_local_hardware():
    assert 'network_access == NETWORK_LOCAL_ONLY and not local_client' in ACCOUNTS
    assert 'network_access == NETWORK_REMOTE_ONLY and not exact_remote_host' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host)' in ACCOUNTS
    assert 'is_local_connection and network_access in {NETWORK_LOCAL_ONLY, NETWORK_LOCAL_REMOTE}' in ACCESS
    assert '"cast_targets": (' in DASH
    assert 'if access.get("local_ha_hardware_allowed")' in DASH


def test_weight_provenance_is_vendor_neutral_and_uses_device_evidence():
    assert 'platform.startswith("garmin")' not in SCALES
    assert 'explicit_scale = any(marker in evidence for marker in scale_markers)' in SCALES
    assert 'composition_hits = sum(1 for marker in composition_markers if marker in sibling_text)' in SCALES
    assert 'explicit_non_scale_device = any(marker in evidence for marker in wearable_markers)' in SCALES
    assert 'composition_hits >= 2 and not explicit_non_scale_device' in SCALES
    assert '"source_integration": provider[:64]' in SCALES
    assert '"source_device": device_name[:96]' in SCALES


def test_smart_tv_platform_selector_is_removed_and_only_real_android_launch_transports_remain():
    assert '${prefix}-platform' not in JS
    assert 'smart_tv_lg' not in JS
    assert 'smart_tv_samsung' not in JS
    assert 'registry_entry.platform == "androidtv_remote"' in DASH
    assert 'registry_entry.platform == "androidtv"' in DASH
    assert '"androidtv_remote_url"' in DASH
    assert '"androidtv_adb"' in DASH
    assert '"remote", "turn_on"' in DASH
    assert '"androidtv", "adb_command"' in DASH
    assert 'shlex.quote(receiver_url)' in DASH
    assert 'async_wait_cast_bootstrap_redeemed(' in DASH
    assert 'launch_error = "receiver_not_connected"' in DASH


def test_ytdlp_exposes_only_items_that_pass_the_browser_playback_resolver():
    search = YTDLP[YTDLP.index('async def async_search'):YTDLP.index('async def async_resolve')]
    assert 'resolve_youtube_audio' in search
    assert 'if bool(row.get("is_live")):' in search
    assert 'list_youtube_playlist_entries, target, 8' in search
    assert 'return row' in search
    resolve = YTDLP[YTDLP.index('async def async_resolve'):]
    assert 'if marker == "live":' in resolve
    assert 'playable: list[tuple[dict[str, Any], Any]] = []' in resolve
    assert 'if isinstance(resolved_item, Exception):' in resolve
    assert 'if not playable:' in resolve
    assert 'playlist_items' in resolve


def test_cast_media_browser_is_viewport_contained_without_losing_existing_performance_guards():
    assert ':host([fitness-cast-receiver]) .browser-modal{width:min(1180px,calc(100vw - 24px))' in JS
    assert 'overflow-y:auto!important;overflow-x:hidden!important;contain:content' in JS
    assert ':host([fitness-cast-receiver]) .browser-modal .media-row{width:100%!important' in JS
    assert 'const FITNESS_TV_CAST_LEGACY_ENGINE = (() =>' in JS
    assert 'this.toggleAttribute("fitness-cast-lite", FITNESS_TV_CAST_LEGACY_ENGINE);' in JS
    # Keep the low-churn receiver path: state snapshots are conditional and the
    # old-TV compatibility path disables expensive animation/blur work.
    assert 'FITNESS_TV_CAST_LEGACY_ENGINE?"0px":preset.blur' in JS
    assert 'fitness-animations' in JS

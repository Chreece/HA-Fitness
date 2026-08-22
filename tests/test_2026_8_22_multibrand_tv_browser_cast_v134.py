from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_browser_receiver_supports_multibrand_tv_and_admin_overview_without_fake_platform_modes():
    assert '"fitness/tv/browser_receiver"' in DASHBOARD
    assert 'overview:Boolean(overview)' in FRONTEND
    # LG/Samsung/other browser TVs all consume the same hardened URL, so there
    # is no cosmetic platform selector. Only a real launch transport is selectable.
    assert '${prefix}-platform' not in FRONTEND
    assert 'overview-smart-tv-platform' not in FRONTEND
    assert 'androidtv_remote_url' in DASHBOARD
    assert 'androidtv_adb' in DASHBOARD
    assert 'smart_tv_force_open' in FRONTEND


def test_browser_receiver_ticket_matches_request_network_and_overview_keeps_admin_actions_restricted_to_fitness():
    # Manual browser receivers may be issued for local or remote Fitness sessions.
    # Only HA-managed automatic Android/Google TV launch is LAN-only.
    assert 'if launch_entity_id or launch_method:' in DASHBOARD
    assert 'if not access.get("local_ha_hardware_allowed"):' in DASHBOARD
    assert 'Automatic TV launch is available only on the Home Assistant local network' in DASHBOARD
    assert '"local_only" if access.get("is_local_connection") else "remote_only"' in DASHBOARD
    assert 'network_access: str = NETWORK_LOCAL_ONLY' in ACCOUNTS
    assert '"network_access": network_access' in ACCOUNTS
    assert 'ticket_network == NETWORK_LOCAL_ONLY and not _client_is_local(remote)' in ACCOUNTS
    assert 'ticket_network == NETWORK_REMOTE_ONLY and _client_is_local(remote)' in ACCOUNTS
    assert '"_cast_overview_only": overview' in ACCOUNTS
    assert '"fitness/dashboard/config_flow/start"' in ACCOUNTS
    assert '"fitness/dashboard/config_flow/step"' in ACCOUNTS
    assert '"fitness/dashboard/config_flow/cancel"' in ACCOUNTS
    assert 'Fitness command is not available through the restricted portal' in ACCOUNTS


def test_ha_cast_targets_are_never_disclosed_to_remote_sessions():
    block = DASHBOARD[DASHBOARD.index('"cast_targets": ('):DASHBOARD.index('"overview_cast": (')]
    assert 'if access.get("local_ha_hardware_allowed")' in block
    assert 'is_admin' not in block
    assert 'Home Assistant TV control is available only on the local network' in ACCOUNTS


def test_smart_tv_receiver_reuses_restricted_cast_portal_and_local_audio_handoff():
    assert 'issue_cast_bootstrap(' in DASHBOARD
    assert 'hub.expect_local_cast(profile_entry_id, f"smart-tv:' in ACCOUNTS
    assert 'card.setAttribute("fitness-cast-receiver","")' in ACCOUNTS

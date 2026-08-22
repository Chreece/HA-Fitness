from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
DOC = (ROOT / "docs/LOCAL_CAST.md").read_text()


def test_zero_registration_local_cast_uses_published_dashcast_receiver():
    assert 'DASHCAST_APP_ID = "84912283"' in DASH
    assert "DashCastController" in DASH
    assert "controller.load_url(url, force=True" in DASH
    assert "pychromecast.get_chromecasts()" in DASH
    assert "uuid.UUID(str(registry_entry.unique_id))" in DASH
    for forbidden in ("Sony", "192.168.178.", "BRAVIA 4K VH22"):
        assert forbidden not in DASH


def test_dashcast_bootstrap_is_network_scoped_profile_scoped_and_ephemeral():
    assert 'url = "/fitness/cast/{ticket}"' in ACCOUNTS
    assert "_client_is_local(remote)" in ACCOUNTS
    assert "issue_cast_bootstrap" in ACCOUNTS
    assert "async_redeem_cast_bootstrap" in ACCOUNTS
    assert "_ephemeral_cast_accounts" in ACCOUNTS
    assert '"role": ROLE_USER' in ACCOUNTS
    assert 'network_access: str = NETWORK_LOCAL_ONLY' in ACCOUNTS
    assert '"network_access": network_access' in ACCOUNTS
    assert 'ticket_network == NETWORK_LOCAL_ONLY and not _client_is_local(remote)' in ACCOUNTS
    assert 'ticket_network == NETWORK_REMOTE_ONLY and _client_is_local(remote)' in ACCOUNTS
    assert '"profile_entry_id": profile_entry_id' in ACCOUNTS
    assert '"view_profile_entry_ids": []' in ACCOUNTS
    assert "_CAST_BOOTSTRAP_TTL = timedelta(minutes=3)" in ACCOUNTS
    assert "revoke_cast_sessions" in ACCOUNTS


def test_dashcast_receiver_never_receives_home_assistant_credentials():
    launch = DASH[DASH.index("async def _async_dashcast_profile_url"):DASH.index("async def _async_wait_for_cast_receiver_exit")]
    bootstrap = ACCOUNTS[ACCOUNTS.index("class FitnessDashCastBootstrapView"):ACCOUNTS.index("class FitnessPortalLoginView")]
    for secret in ("refresh_token", "access_token", "async_create_access_token", "async_create_refresh_token"):
        assert secret not in launch
        assert secret not in bootstrap
    assert "restricted local Fitness portal" in bootstrap


def test_dashcast_uses_existing_restricted_portal_acl_and_cast_receiver_mode():
    assert "FitnessPortalConnection" in ACCOUNTS
    assert "_run_fitness_handler" in ACCOUNTS
    assert "controller.principal(row)" in ACCOUNTS
    assert "cast_receiver=True" in ACCOUNTS
    assert 'get("fitness_cast_receiver") === "1"' in JS
    assert "?fitness_cast_receiver=1" in DASH


def test_browser_sender_cast_remains_visible_but_manual_custom_receiver_setup_is_hidden():
    assert "const localCastVisible = true;" in JS
    assert 'false && localCastCanConfigure ? `<details class="local-cast-config"' in JS
    assert 'id="cast-local-mode"' in JS  # retained dormant compatibility code
    assert "Google Cast SDK Developer Console" not in DOC
    assert "There is no per-installation receiver registration or app ID." in DOC


def test_existing_official_cast_compatibility_code_remains_available():
    assert 'LOCAL_CAST_APP_ID = "A078F6B0"' in REMOTE
    assert 'LOCAL_CAST_NAMESPACE = "urn:x-cast:com.nabucasa.hast"' in REMOTE
    assert 'type:"connect"' in JS
    assert 'type:"show_lovelace_view"' in JS


def test_local_cast_documentation_matches_zero_setup_architecture():
    assert "public DashCast receiver (application 84912283)" in DOC
    assert "one-time bootstrap ticket" in DOC
    assert "Home Assistant access token" in DOC
    assert "Press **Cast**" in DOC


def test_dashcast_uses_native_single_launch_load_url_and_keeps_sender_alive():
    launch = DASH[DASH.index("def _launch_dashcast_sync"):DASH.index("async def _async_launch_dashcast")]
    assert "controller.load_url(url, force=True)" in launch
    assert "controller.launch(" not in launch
    assert "DASHCAST_POST_LOAD_SETTLE = 15.0" in DASH
    assert "time.sleep(DASHCAST_POST_LOAD_SETTLE)" in launch
    assert "load_url() already performs the DashCast launch internally" in launch
    assert "target.register_handler(controller)" in launch
    assert "target.wait(timeout=15)" in launch


def test_successfully_delivered_dashcast_url_is_not_force_relaunched_when_heartbeat_is_slow():
    cast = DASH[DASH.index("async def async_cast_tv_dashboard"):]
    assert "Fitness TV DashCast URL was delivered on %s but no live Fitness receiver heartbeat arrived" in cast
    marker = cast.index("Fitness TV DashCast URL was delivered on %s but no live Fitness receiver heartbeat arrived")
    tail = cast[marker:marker + 1000]
    assert "break" in tail


def test_force_navigation_never_requires_dashcast_app_id_after_url_delivery():
    cast = DASH[DASH.index("async def async_cast_tv_dashboard"):]
    delivered = cast.index("launched = await _async_launch_dashcast")
    heartbeat = cast.index("cast_client = await hub.async_wait_cast_active", delivered)
    post_delivery = cast[delivered:heartbeat]
    assert "_async_wait_for_cast_receiver_launch" not in post_delivery
    assert "app-id persistence is *not* a valid post-load success" in cast
    assert "timeout=28.0 if started_off and attempt == 1 else 24.0" in cast
    warning = cast.index("Fitness TV DashCast URL was delivered on %s but no live Fitness receiver heartbeat arrived")
    assert "break" in cast[warning:warning + 800]


def test_dashcast_portal_does_not_depend_on_tv_cookie_storage():
    assert 'def _cast_session_token_from_request(self, request: web.Request) -> str:' in ACCOUNTS
    assert 'request.headers.get("X-Fitness-Cast-Ticket")' in ACCOUNTS
    assert 'or self._cast_session_token_from_request(request)' in ACCOUNTS
    assert 'const castTicket=castPortal?' in ACCOUNTS
    assert '"X-Fitness-Cast-Ticket":castTicket' in ACCOUNTS
    assert 'const headers={{...castHeaders()}}' in ACCOUNTS
    assert 'headers}});if(r.status===304)return;' in ACCOUNTS


def test_dashcast_bootstrap_heartbeats_before_full_dashboard_mount():
    portal = ACCOUNTS[ACCOUNTS.index('def _portal_app_page('):ACCOUNTS.index('class FitnessDashCastBootstrapView')]
    assert 'async function armCastBootstrap()' in portal
    assert 'type:"fitness/tv/heartbeat"' in portal
    assert 'is_cast_receiver:true' in portal
    start = portal.index('async function startPortal()')
    heartbeat = portal.index('await armCastBootstrap()', start)
    mount = portal.index('mount(currentProfile)', start)
    assert heartbeat < mount
    assert 'window.__fitnessTvClientId=clientId' in portal


def test_dashcast_dynamic_route_handler_accepts_ticket_path_argument():
    bootstrap = ACCOUNTS[ACCOUNTS.index("class FitnessDashCastBootstrapView"):ACCOUNTS.index("class FitnessPortalLoginView")]
    assert 'async def get(self, request: web.Request, ticket: str) -> web.Response:' in bootstrap
    assert 'request, str(ticket or "")' in bootstrap
    assert 'request.match_info.get("ticket")' not in bootstrap

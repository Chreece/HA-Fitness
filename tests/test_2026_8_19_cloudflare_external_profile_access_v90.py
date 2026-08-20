from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
CLOUDFLARE = (ROOT / "custom_components/fitness/cloudflare_dns.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DOC = (ROOT / "docs/REMOTE_ACCESS.md").read_text()


def test_cloudflare_dns_adapter_is_bounded_dns_only_and_ownership_safe():
    assert '"https://api.cloudflare.com/client/v4"' in CLOUDFLARE
    assert 'asyncio.timeout(_REQUEST_TIMEOUT)' in CLOUDFLARE
    assert '"Authorization": f"Bearer {self.token}"' in CLOUDFLARE
    assert '"type": "A"' in CLOUDFLARE
    assert '"proxied": False' in CLOUDFLARE
    assert '"ttl": 1' in CLOUDFLARE
    assert '"POST", f"/zones/{zone_id}/dns_records"' in CLOUDFLARE
    assert '"PATCH",' in CLOUDFLARE
    assert '"DELETE", f"/zones/{zone_id}/dns_records/{row.record_id}"' in CLOUDFLARE
    assert 'raise CloudflareDNSError("cloudflare_dns_name_in_use")' in CLOUDFLARE
    assert 'if records:' in CLOUDFLARE


def test_cloudflare_secret_is_private_and_never_returned_in_admin_snapshot():
    assert 'private=True' in ACCESS
    snapshot = ACCESS[ACCESS.index('async def async_admin_snapshot'):ACCESS.index('async def async_set_access_settings')]
    assert '"api_token_configured"' in snapshot
    assert '"api_token":' not in snapshot
    assert 'DEFAULT_CLOUDFLARE_ZONE = ""' in ACCESS
    assert 'DEFAULT_CLOUDFLARE_BASE_DOMAIN = ""' in ACCESS
    assert 'address.version != 4 or not address.is_global' in ACCESS


def test_global_cloudflare_websocket_and_admin_ui_are_first_class():
    for field in (
        'cloudflare_zone',
        'cloudflare_base_domain',
        'cloudflare_api_token',
        'cloudflare_record_target',
    ):
        assert field in ACCESS
    assert 'type:"fitness/access/settings/save"' in JS
    assert 'id="access-cloudflare-zone"' in JS
    assert 'id="access-base-domain"' in JS
    assert 'id="access-cloudflare-target"' in JS
    assert 'id="access-cloudflare-token"' in JS
    assert 'class="icon-tool cloudflare-info-toggle"' in JS
    assert 'cloudflare_info_steps' in DASH


def test_profile_external_access_creates_and_disables_managed_hostnames():
    assert 'async def _async_set_external_profile' in ACCESS
    assert 'Managed by HA-Fitness profile' in ACCESS  # private DNS ledger ownership marker
    assert 'remote_slug' in ACCOUNTS
    assert 'should_publish = wants_remote and router_ready' in ACCOUNTS
    assert 'await access._async_set_external_profile' in ACCOUNTS
    assert 'cloudflare_cleanup' in ACCOUNTS
    assert 'cloudflare_publish' in ACCOUNTS
    assert 'async_reconcile_remote_dns' in ACCOUNTS

def test_profile_settings_have_external_switch_subdomain_url_and_help_for_both_surfaces():
    assert 'const _fitnessExternalAccessMarkup' not in JS
    assert 'id="cfg-external-enabled"' not in JS
    assert 'id="cfg-external-subdomain"' not in JS
    assert 'type:"fitness/access/external/save"' not in JS
    assert 'data-account-slug' in JS
    assert 'data-account-url' in JS
    assert 'class="icon-tool cloudflare-info-toggle"' in JS
    assert 'remote_subdomain_hint' in JS

def test_host_router_maps_exact_hostname_to_exact_profile_and_blocks_disabled_namespace():
    assert 'def async_register_fitness_portal_routing' in ACCOUNTS
    assert 'remote_account = controller.account_by_remote_host(request.host)' in ACCOUNTS
    assert 'if host != base and remote_account is None:' in ACCOUNTS
    assert 'raise web.HTTPNotFound(text="Fitness remote account is disabled")' in ACCOUNTS
    assert 'raise web.HTTPFound(location="/fitness-auth/login")' in ACCOUNTS
    assert 'raise web.HTTPFound(location="/fitness-auth/app")' in ACCOUNTS
    assert 'raise web.HTTPNotFound(text="This hostname serves the restricted HA-Fitness portal only")' in ACCOUNTS

def test_dashboard_contract_exposes_secret_free_external_state_and_v90_cache():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert '?v=unreleased-110' in DASH
    assert '"frontend_version": "unreleased-110"' in DASH
    assert '"api_token_configured"' in ACCESS
    assert '"api_token":' not in ACCESS[ACCESS.index('async def async_admin_snapshot'):ACCESS.index('async def async_set_access_settings')]

def test_remote_access_document_matches_managed_cloudflare_model():
    for phrase in (
        'Cloudflare external access',
        'DNS-only A record',
        'does not edit nginx, Certbot',
        'info button',
        'https://chreece.fitness.example.com',
        'independent Fitness account',
        'first-time password',
    ):
        assert phrase in DOC

def test_external_access_relaxes_and_restores_ha_local_only_gate_for_local_role():
    assert 'async def _async_sync_bound_profile_user_local_only' in ACCESS
    helper = ACCESS[ACCESS.index('async def _async_sync_bound_profile_user_local_only'):ACCESS.index('def _external_profile_host')]
    assert 'Fitness accounts no longer mutate HA users' in helper
    assert 'async_update_user' not in helper
    assert 'local_only' in helper
    assert 'if role == ROLE_LOCAL and not _client_is_local(remote):' in ACCOUNTS
    assert 'if role == ROLE_ADMIN and not _client_is_local(remote) and not exact_remote_host:' in ACCOUNTS
    assert 'remote_host_mismatch' in ACCOUNTS

def test_active_external_profiles_cannot_orphan_dns_by_clearing_token():
    settings = ACCESS[
        ACCESS.index('async def async_set_access_settings'):
        ACCESS.index('async def async_set_remote_base_domain')
    ]
    assert 'external_enabled = any(' in settings
    assert 'if external_enabled and (critical_changed or not token):' in settings
    assert 'raise ValueError("cloudflare_settings_in_use")' in settings

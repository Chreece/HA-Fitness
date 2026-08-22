from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DOC = (ROOT / "docs/REMOTE_ACCESS.md").read_text(encoding="utf-8")
TRANSLATIONS = (ROOT / "custom_components/fitness/dashboard_translations.py").read_text(encoding="utf-8")


def test_installation_has_no_private_domain_default_or_reference():
    corpus = "\n".join((ACCESS, ACCOUNTS, JS, DOC, TRANSLATIONS))
    assert ("hass" + ".gr") not in corpus
    assert 'DEFAULT_CLOUDFLARE_ZONE = ""' in ACCESS
    assert 'DEFAULT_CLOUDFLARE_BASE_DOMAIN = ""' in ACCESS
    assert 'placeholder="example.com"' in JS
    assert 'placeholder="fitness.example.com"' in JS


def test_admin_settings_explain_reverse_proxy_tls_and_host_preservation():
    assert 'remote_server_setup_title' in JS
    assert 'remote_server_setup_hint' in JS
    assert 'nginx' in JS
    assert 'Certbot' in JS
    assert 'original Host header' in JS
    assert 'DNS alone is not enough' in DOC
    assert 'proxy_set_header Host $host;' in DOC


def test_independent_admin_can_optionally_own_a_remote_hostname():
    assert 'def _account_remote_enabled' in ACCOUNTS
    assert 'network in {NETWORK_REMOTE_ONLY, NETWORK_LOCAL_REMOTE}' in ACCOUNTS
    assert 'vol.Required("network_access"): vol.In(sorted(NETWORK_ACCESS_MODES))' in ACCOUNTS
    assert 'data-account-network' in JS
    assert 'access._async_set_external_account' in ACCOUNTS
    assert 'async def _async_set_external_account' in ACCESS
    assert 'external_accounts' in ACCESS

def test_remote_admin_is_full_admin_but_still_exact_host_confined_from_internet():
    assert '"is_admin": str(row.get("role") or "") in {"admin", "admin_user"}' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_ONLY and not local_client' in ACCOUNTS
    assert 'network_access == NETWORK_REMOTE_ONLY and not exact_remote_host' in ACCOUNTS
    assert 'network_access == NETWORK_LOCAL_REMOTE and not (local_client or exact_remote_host)' in ACCOUNTS

def test_remote_admin_labels_exist_in_every_supported_dashboard_language():
    for key in (
        'admin_remote_access', 'admin_remote_access_hint', 'role_admin_remote_hint',
        'remote_base_domain_missing', 'remote_server_setup_title', 'remote_server_setup_hint',
    ):
        assert TRANSLATIONS.count(f'"{key}"') >= 15


def test_v97_cache_revision_is_consistent():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS

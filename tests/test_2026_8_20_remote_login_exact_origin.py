from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_remote_login_uses_host_only_form_nonce_instead_of_proxy_sensitive_origin_headers():
    assert '_LOGIN_CSRF_COOKIE = "__Host-fitness_login_csrf"' in ACCOUNTS
    assert 'name="login_csrf" value="{html.escape(login_csrf)}"' in ACCOUNTS
    assert 'samesite="Strict"' in ACCOUNTS
    assert 'httponly=True' in ACCOUNTS
    helper = ACCOUNTS[ACCOUNTS.index("def _login_csrf_valid"):ACCOUNTS.index("async def _bounded_form_body")]
    assert 'request.cookies.get(_LOGIN_CSRF_COOKIE)' in helper
    assert 'secrets.compare_digest(cookie, submitted)' in helper
    login = ACCOUNTS[ACCOUNTS.index("class FitnessPortalLoginView"):ACCOUNTS.index("class FitnessPortalPasswordView")]
    assert 'if not _login_csrf_valid(request, form):' in login
    assert 'if not _same_origin_form(request):' not in login


def test_first_password_change_uses_authenticated_session_csrf():
    password = ACCOUNTS[ACCOUNTS.index("class FitnessPortalPasswordView"):ACCOUNTS.index("class FitnessPortalAppView")]
    assert '_password_page(row, csrf_token=session.csrf)' in password
    assert 'secrets.compare_digest(submitted_csrf, _session.csrf)' in password
    assert 'if not _same_origin_form(request):' not in password


def test_remote_hostname_still_selects_account_server_side():
    login = ACCOUNTS[ACCOUNTS.index("class FitnessPortalLoginView"):ACCOUNTS.index("class FitnessPortalPasswordView")]
    assert 'remote_account = controller.account_by_remote_host(request.host)' in login
    assert 'str(remote_account.get("username") or "")' in login
    assert 'if remote_account is not None' in login

from pathlib import Path

DASH = Path("custom_components/fitness/dashboard.py").read_text()

def test_dashboard_reconcile_is_rate_limited_and_not_request_spam():
    assert '_RECONCILE_MIN_INTERVAL = 300.0' in DASH
    assert 'if not force and last and (now - last) < _RECONCILE_MIN_INTERVAL:' in DASH
    assert 'domain_data[_RECONCILE_LAST_KEY] = asyncio.get_running_loop().time()' in DASH
    assert '_schedule_dashboard_reconcile(hass)' in DASH

def test_unchanged_dashboard_reconciliation_does_not_spam_info_logs():
    assert '_LOGGER.debug("Fitness dashboard resource already canonical: %s", _RESOURCE_URL)' in DASH
    assert '_LOGGER.debug(\n        "Fitness TV dashboard ready at /%s with %d explicit Cast-compatible views"' in DASH

def test_v129_cache_contract():
    front = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()
    accounts = Path("custom_components/fitness/fitness_accounts.py").read_text()
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in front
    assert '?v=unreleased-138' in DASH
    assert 'frontend_version = "unreleased-138"' in accounts

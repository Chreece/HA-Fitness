from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_remote_host_router_can_activate_after_aiohttp_freezes_middlewares():
    assert "def _async_install_portal_middleware" in ACCOUNTS
    assert 'app.middlewares.append(middleware)' in ACCOUNTS
    assert 'app._middlewares_handlers = ((middleware, True), *prepared_tuple)' in ACCOUNTS
    assert 'app._run_middlewares = True' in ACCOUNTS
    assert 'app._run_middlewares = old_run_middlewares' in ACCOUNTS
    assert '"_cached_build_middleware"' in ACCOUNTS
    assert 'cache.cache_clear()' in ACCOUNTS
    assert 'return "registered_after_freeze"' in ACCOUNTS
    assert 'if data.get(PORTAL_MIDDLEWARE_KEY) is True:' in ACCOUNTS
    assert 'will activate after the next Home Assistant restart' not in ACCOUNTS


def test_remote_dns_fails_closed_when_live_host_router_is_unavailable():
    assert 'router_ready = self.hass.data.get(DOMAIN, {}).get(PORTAL_MIDDLEWARE_KEY) is True' in ACCOUNTS
    assert 'should_publish = wants_remote and router_ready' in ACCOUNTS
    assert ACCOUNTS.count('"host_router_unavailable"') >= 4
    reconcile = ACCOUNTS[ACCOUNTS.index('async def async_reconcile_remote_dns'):ACCOUNTS.index('# ---------------------------------------------------------------------------\n# Restricted backend bridge')]
    assert 'if not router_ready:' in reconcile
    assert 'await _set_dns(row, False)' in reconcile
    assert 'enabled=enabled, subdomain=(slug if enabled else None)' in reconcile
    assert 'return' in reconcile

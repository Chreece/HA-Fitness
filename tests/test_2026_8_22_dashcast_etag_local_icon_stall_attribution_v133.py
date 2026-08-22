from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
WATCHDOG = (ROOT / "custom_components/fitness/live/stall_watchdog.py").read_text(encoding="utf-8")


def test_dashcast_receiver_does_not_fetch_remote_icon_assets():
    assert '/fitness/frontend/fitness-mdi-icons.js?v=7.4.47-fitness-1' in ACCOUNTS
    assert 'const fitnessPortalIconPath=' in ACCOUNTS
    assert 'const fitnessPortalGlyph=(key)' in ACCOUNTS
    assert 'FITNESS_PORTAL_REMOTE_ICONS' not in ACCOUNTS
    assert 'cdn.jsdelivr.net' not in ACCOUNTS


def test_dashcast_state_poll_uses_etag_and_less_aggressive_interval():
    assert 'let statesRefreshInFlight=false;let statesEtag="";' in ACCOUNTS
    assert 'headers["If-None-Match"]=statesEtag' in ACCOUNTS
    assert 'if(r.status===304)return;' in ACCOUNTS
    assert 'setInterval(refreshStates,castPortal?2500:3000)' in ACCOUNTS
    assert 'hashlib.sha256' in ACCOUNTS
    assert 'request.headers.get("If-None-Match")' in ACCOUNTS
    assert 'status=304' in ACCOUNTS


def test_external_stall_log_names_observed_component_without_blame_on_fitness():
    assert 'def _external_component(stack: str) -> str:' in WATCHDOG
    assert 'observer=fitness; culprit=custom_components.%s;' in WATCHDOG
    assert 'MainThread is not executing Fitness code' in WATCHDOG

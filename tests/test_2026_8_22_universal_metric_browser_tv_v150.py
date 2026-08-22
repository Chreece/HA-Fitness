from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_browser_tv_portal_is_detected_by_the_same_receiver_runtime_as_dashcast():
    start = FRONTEND.index("const FITNESS_TV_CAST_RECEIVER = (() =>")
    block = FRONTEND[start:start + 1200]
    assert 'const portal = Boolean(globalThis.window?.__FITNESS_CAST_PORTAL__);' in block
    assert 'return host === "cast.home-assistant.io" || direct || portal;' in block
    assert 'window.__FITNESS_CAST_PORTAL__={cast_receiver_js}' in ACCOUNTS
    assert 'if(castPortal)card.setAttribute("fitness-cast-receiver","")' in ACCOUNTS


def test_browser_tv_and_dashcast_share_dense_masonry_and_card_surface_path():
    assert 'const stableDesktopGrid = !FITNESS_TV_CAST_RECEIVER' in FRONTEND
    assert 'const gap = Math.max(6, Number.parseFloat(getComputedStyle(this).getPropertyValue("--fitness-theme-gap")) || 12);' in FRONTEND
    assert 'card.toggleAttribute("fitness-tv-display", FITNESS_TV_CAST_RECEIVER);' in FRONTEND
    assert ':host([fitness-tv-display]) > ha-card{' in FRONTEND
    assert 'background-color:var(--ha-card-background,var(--card-background-color,#1d1f22))!important' in FRONTEND


def test_metric_selection_is_latest_timestamp_only_and_vendor_neutral():
    start = MANAGER.index("def canonical_metric_observation")
    end = MANAGER.index("def canonical_wellness_observation", start)
    block = MANAGER[start:end]
    assert "Source type never participates in ranking." in block
    assert "source quality or vendor priority" in block
    assert "_metric_observation_timestamp" in block
    assert "self.metric_history" in block
    assert "self.device_intraday_history" in block
    assert "self.fitness_test_metric_observations()" in block
    assert '"vo2_max", "vo2max"' in MANAGER
    assert '"threshold_power", "ftp_running"' in MANAGER
    for forbidden in ("source_type.startswith(\"direct_\")", "quality = 50", "quality = 45", "quality = 40"):
        assert forbidden not in MANAGER


def test_undated_values_are_fallbacks_not_fake_now_observations():
    assert "An undated provider/config value is still a" in MANAGER
    assert "return None" in MANAGER[MANAGER.index("def _source_stamp"):MANAGER.index("for metric in metric_keys", MANAGER.index("def _source_stamp"))]
    assert 'history_metric = observation.get("evaluation_metric") or observation.get("metric")' in MANAGER


def test_v150_cache_contract():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS

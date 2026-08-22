from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def test_last_media_is_prepared_on_dashboard_load_and_companion_resume():
    assert "async _prepareRestoredMedia({autoplay = false} = {})" in JS
    assert "void this._prepareRestoredMedia({autoplay:FITNESS_TV_CAST_RECEIVER})" in JS
    assert "void this._prepareRestoredMedia({autoplay:false})" in JS
    assert 'this._musicAudio.preload = "auto"' in JS
    assert 'this._musicAudio.addEventListener("loadedmetadata", seekWhenReady, {once:true})' in JS


def test_route_card_keeps_metrics_on_map_edges_and_route_center_clear():
    assert "const overlayReserve = summary.length" in JS
    assert 'class="map-metrics map-metrics-left"' in JS
    assert 'class="map-metrics map-metrics-right"' in JS
    assert 'class="map-metric entity-link"' in JS
    assert ".map-metric{pointer-events:auto" in JS


def test_today_overview_prioritizes_available_steps():
    assert "const stepsId = e.device_steps" in JS
    assert 'add("device_steps"' in JS


def test_daily_and_seven_day_ai_cards_accept_bounded_user_text():
    assert 'vol.Optional("user_text", default=""): vol.All(str, vol.Length(max=2000))' in DASHBOARD
    assert 'def _daily_training_plan_prompt(self, user_text: str = "")' in MANAGER
    assert 'def _training_plan_prompt(self, user_text: str = "")' in MANAGER
    assert '"user_request": user_text or None' in MANAGER
    assert 'user_text:String(this._aiUserText||"").trim().slice(0,2000)' in JS
    assert 'class="ai-user-text"' in JS

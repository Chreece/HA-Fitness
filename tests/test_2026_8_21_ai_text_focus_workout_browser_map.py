from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_ai_text_editing_survives_live_hass_updates_and_gestures():
    assert "Never replace a card's shadow DOM while the user is typing" in JS
    assert 'this.shadowRoot?.activeElement' in JS
    assert 'active.addEventListener("blur", () =>' in JS
    assert '["pointerdown","pointerup","click","dblclick","touchstart","touchend","keydown","keyup","keypress"]' in JS
    assert "editor.addEventListener(\"input\"" in JS or "editor.addEventListener('input'" in JS


def test_workout_browser_map_uses_left_and_right_metric_columns():
    assert 'factItems=String(factsMarkup||"").match(' in JS
    assert 'class="map-metrics map-metrics-left"' in JS
    assert 'class="map-metrics map-metrics-right"' in JS
    assert '.map-metrics-left{left:8px}' in JS
    assert '.map-metrics-right{right:8px}' in JS
    assert 'sideReserve=factItems.length?' in JS
    assert '_fitMapState(pts,width,height,sideReserve)' in JS

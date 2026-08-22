from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH=(ROOT/"custom_components/fitness/dashboard.py").read_text()

def test_workout_map_recovers_route_from_provider_provenance():
    assert "const stack=[extra,providerValues]" in JS
    assert 'track = _route_points(data.get("gps_track")) or _route_points(extra)' in DASH
    assert 'track = _route_points(data.get("provider_values") or {})' in DASH
    assert 'extra["gps_track"] = track' in DASH

def test_desktop_masonry_does_not_feed_natural_card_height_back_into_ai_cards():
    assert 'if (userSized) {' in JS
    assert 'card.style.setProperty("--fitness-natural-card-min-height", "0px")' in JS
    assert 'if (Math.abs(width - Number(this._lastObservedGridWidth || 0)) < 1) return;' in JS

def test_remote_sessions_do_not_receive_or_render_home_assistant_speakers():
    assert 'if access.get("local_ha_hardware_allowed")' in DASH
    assert 'const audioOutputs = (localHaHardwareAllowed && Array.isArray(this._audioOutputs)' in JS
    assert '.audio-output-field>span>strong,.audio-output-field>span>small{display:block}' in JS

def test_v119_cache_contract():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '?v=unreleased-138' in DASH

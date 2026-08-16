from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_vo2_prediction_is_centered_and_zero_prediction_is_not_authoritative():
    assert 'predictedAttr != null && predictedAttr > 0' in FRONTEND
    assert 'const predictedMarker = useAbsoluteVo2Scale\n      ? 50' in FRONTEND
    assert 'vo2ScaleMagnitude * 0.10' in FRONTEND
    assert 'Math.abs(current - predictedAbsolute) * 1.05' in FRONTEND
    assert '`${predictedAbsolute.toFixed(1)} ${l.predicted || "Predicted"}`' in FRONTEND


def test_vo2_history_zoom_ignores_distant_prediction():
    assert 'const measuredVals = [...series.map(x=>x.v), trendStart, trendEnd];' in FRONTEND
    assert 'predictedAbsolute' not in FRONTEND.split('const measuredVals = [...series.map(x=>x.v), trendStart, trendEnd];', 1)[1].split('let lo =', 1)[0]
    assert 'const predictedInViewport' in FRONTEND
    assert 'l.below_zoom || "below zoom"' in FRONTEND
    assert 'l.above_zoom || "above zoom"' in FRONTEND


def test_dashboard_resource_bumped():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in BACKEND

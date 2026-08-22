from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_single_live_metric_and_control_are_centered_on_phone():
    assert 'const allMetricItems = [...metrics, ...sensorMetrics];' in JS
    assert 'live-grid${allMetricItems.length === 1 ? " single" : ""}' in JS
    assert 'live-controls${controlItems.length === 1 ? " single" : ""}' in JS
    assert '.live-grid.single,.live-controls.single{grid-template-columns:1fr;width:min(100%,280px);margin-left:auto;margin-right:auto}' in JS


def test_multiple_live_items_keep_responsive_grid():
    assert '.live-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:6px}' in JS
    assert '.live-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin-top:6px}' in JS


def test_frontend_cache_bumped_for_centering_fix():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS

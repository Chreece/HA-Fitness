from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_dashboard_resource_version_bumped():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-89"' in FRONTEND
    assert '?v=unreleased-89' in BACKEND


def test_vo2_progress_uses_absolute_current_marker_and_predicted_reference():
    assert 'const useAbsoluteVo2Scale = current != null && current > 0 && predictedAbsolute != null && predictedAbsolute > 0;' in FRONTEND
    assert '((current - progressMin) / progressSpan) * 100' in FRONTEND
    assert 'const predictedMarker = useAbsoluteVo2Scale' in FRONTEND
    assert '? 50' in FRONTEND
    assert 'class="vo2-reference"' in FRONTEND
    assert 'class="vo2-marker"' in FRONTEND
    assert "l.predicted_marker" in FRONTEND
    assert "l.current_marker" in FRONTEND
    assert 'background:#fff' in FRONTEND
    assert '.vo2-marker:after' in FRONTEND


def test_vo2_history_discards_missing_invalid_and_nonpositive_values():
    assert 'x.v != null && x.v > 0 && Number.isFinite(x.t)' in FRONTEND
    assert '.sort((a,b) => a.t - b.t)' in FRONTEND
    assert 'const xPos = t => ((t-startT)/timeSpan)*100;' in FRONTEND


def test_vo2_history_has_pointer_crosshair_and_value_tooltip():
    assert 'class="history-cursor"' in FRONTEND
    assert 'class="cursor-line"' in FRONTEND
    assert 'class="history-tooltip"' in FRONTEND
    assert 'svg.addEventListener("pointermove", move);' in FRONTEND
    assert 'mL/kg/min</strong>' in FRONTEND
    assert 'new Intl.DateTimeFormat' in FRONTEND


def test_hrv_baseline_bar_is_not_gated_by_recovery_time_panel():
    # The bar is rendered after readiness components, outside the recoveryTime-only block.
    marker = '${componentRows ? `<div class="components entity-link"'
    start = FRONTEND.index(marker)
    segment = FRONTEND[start:start + 900]
    assert '${hrvBaselineBar}' in segment
    assert 'hrvBaselineBar || hrvVs == null' in segment


def test_hrv_latest_can_use_autonomic_evidence_when_source_route_is_missing():
    assert 'hrvSource?.canonicalValue ?? _fitnessNumber(_fitnessAttr(autonomic, "sleep_hrv_latest_ms"))' in FRONTEND
    assert 'hrvBaselineNights >= 14' in FRONTEND


def test_recovery_component_labels_wrap_instead_of_ellipsis():
    assert 'title="${_fitnessEscape(label)}"' in FRONTEND
    assert '.component span{font-size:10px;line-height:1.2' in FRONTEND
    assert 'text-overflow:ellipsis;white-space:nowrap' not in FRONTEND[FRONTEND.index('.component span{'):FRONTEND.index('.component strong{')]

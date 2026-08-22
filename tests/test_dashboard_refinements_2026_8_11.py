from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")

def test_single_frontend_module_contract_is_preserved():
    assert "fitness-dashboard-2026.8.11.js" not in BACKEND
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in BACKEND
    front = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', FRONTEND).group(1)
    back = re.search(r'\?v=([^"}]+)', BACKEND).group(1)
    assert front == back == "unreleased-138"

def test_sleep_total_excludes_awake_regression():
    assert "asleepStageTotal" in FRONTEND
    assert "const awakeItem = rawValues.find" in FRONTEND
    assert "const total = asleepStageTotal;" in FRONTEND
    assert 252 + 115 + 81 == 448
    assert 227 + 252 + 115 + 81 == 675

def test_readiness_is_integrated_into_next_workout():
    assert 'class="recovery-score-stack"' in FRONTEND
    assert 'kind:"readiness"' in FRONTEND
    assert '${readinessStack}' in FRONTEND
    assert '${recoveryProgressBar ?' in FRONTEND

def test_numeric_gauge_context_and_hr_baseline_tones():
    for token in ["axis-values", "current-marker", "baselineTone", "progress-values", "history-values", "load-scale-values"]:
        assert token in FRONTEND

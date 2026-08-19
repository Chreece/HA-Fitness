from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (
    ROOT / "custom_components/fitness/sensor.py"
).read_text(encoding="utf-8")
EXPLANATIONS = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")


def test_all_non_ai_evaluation_metrics_have_specific_catalog_entry():
    metrics = re.findall(
        r'Desc\(key="[^"]+".*?kind="evaluation", metric="([^"]+)"',
        SENSOR,
    )
    for metric in metrics:
        if metric in {"ai_general", "ai_workout", "ai_daily_plan", "ai_live_analysis", "evaluation_data"}:
            continue
        assert f'"{metric}": (' in EXPLANATIONS, metric

"""Sleep pie must represent actual sleep only, never Awake time."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


def sleep_percentages(light, deep, rem):
    total = light + deep + rem
    return [round(light / total * 100), round(deep / total * 100), round(rem / total * 100)]


def test_exact_screenshot_sleep_arithmetic():
    awake = 227
    light = 252
    deep = 115
    rem = 81

    assert light + deep + rem == 448
    assert awake + light + deep + rem == 675
    assert sleep_percentages(light, deep, rem) == [56, 26, 18]
    assert sum(sleep_percentages(light, deep, rem)) == 100


def test_awake_is_removed_from_pie_data():
    assert "const awakeItem = rawValues.find" in FRONTEND
    assert "const awakeItem = rawValues.find" in FRONTEND
    assert "const values = stageItems.map" in FRONTEND
    assert "const total = asleepStageTotal;" in FRONTEND
    assert "const stops = values.map" in FRONTEND


def test_center_is_exact_sum_of_visible_sleep_stages():
    assert "const effectiveTotalMinutes = asleepStageTotal > 0" in FRONTEND
    assert "const total = asleepStageTotal;" in FRONTEND


def test_awake_is_separate_duration_only_row():
    assert 'class="awake-row entity-link"' in FRONTEND
    assert 'mdi:eye-outline' in FRONTEND
    awake_template = FRONTEND.split("const awakeRow =", 1)[1].split(
        "const summary =", 1
    )[0]
    assert "pct" not in awake_template
    assert '_formatMinutes(awakeItem.value, "min")' in awake_template


def test_sleep_stage_percentages_are_normalized_against_sleep_only():
    legend = FRONTEND.split("const legend =", 1)[1].split(
        "const awakeRow =", 1
    )[0]
    assert "item.value / total * 100" in legend
    assert "const total = asleepStageTotal;" in FRONTEND


def test_backend_resource_contract_is_unchanged():
    BACKEND = (
        ROOT / "custom_components/fitness/dashboard.py"
    ).read_text(encoding="utf-8")
    assert 'const FITNESS_DASHBOARD_VERSION = "2026.8.11.14";' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.14"' in BACKEND

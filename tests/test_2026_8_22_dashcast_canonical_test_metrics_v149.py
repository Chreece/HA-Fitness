from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")


def _load_test_results_module():
    """Load the deterministic scorer without importing Home Assistant."""
    package_name = "fitness_v149_testpkg"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "custom_components/fitness")]
    sys.modules[package_name] = package

    const_spec = importlib.util.spec_from_file_location(
        f"{package_name}.const", ROOT / "custom_components/fitness/const.py"
    )
    const = importlib.util.module_from_spec(const_spec)
    sys.modules[f"{package_name}.const"] = const
    assert const_spec.loader is not None
    const_spec.loader.exec_module(const)

    results_spec = importlib.util.spec_from_file_location(
        f"{package_name}.fitness_test_results",
        ROOT / "custom_components/fitness/fitness_test_results.py",
    )
    results = importlib.util.module_from_spec(results_spec)
    sys.modules[f"{package_name}.fitness_test_results"] = results
    assert results_spec.loader is not None
    results_spec.loader.exec_module(results)
    return results


def test_dashcast_uses_dense_measured_masonry_not_v148_flex_rows():
    assert "if (FITNESS_TV_CAST_RECEIVER && !this._layoutEditing)" not in FRONTEND
    assert 'grid.style.setProperty("display", "flex")' not in FRONTEND
    assert "const castScale = 1;" in FRONTEND
    assert "const scale = 1;" in FRONTEND
    assert "const stableDesktopGrid = !FITNESS_TV_CAST_RECEIVER" in FRONTEND
    assert "skyline" in FRONTEND


def test_dashcast_cards_get_an_opaque_theme_surface_inside_each_shadow_root():
    assert ":host([fitness-tv-display]) > ha-card{" in FRONTEND
    assert "background-color:var(--ha-card-background,var(--card-background-color,#1d1f22))!important" in FRONTEND
    assert 'card.toggleAttribute("fitness-tv-display", FITNESS_TV_CAST_RECEIVER);' in FRONTEND
    assert 'customElements.define("ha-card",class extends HTMLElement' in ACCOUNTS
    assert 'this.style.backgroundColor="var(--ha-card-background,var(--card-background-color,#1d1f22))"' in ACCOUNTS


def test_dashcast_cache_contract_is_bumped_for_tv_browsers():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS


def test_fitness_test_result_publishes_non_destructive_vo2max_observation_with_reference():
    results = _load_test_results_module()
    result = {
        "test_id": "running_cooper_12min",
        "completed_at": "2026-08-22T19:30:00+00:00",
        "status": "scored",
        "primary": {"kind": "distance", "value": 2700.0, "unit": "m"},
        "metrics": [
            {"kind": "estimated_vo2max", "value": 49.073, "unit": "mL/kg/min"}
        ],
        "reference": {
            "title": "A Means of Assessing Maximal Oxygen Intake",
            "url": "https://pubmed.ncbi.nlm.nih.gov/6018803/",
        },
    }
    observations = results.fitness_test_metric_observations(result)
    assert observations == [
        {
            "metric": "vo2_max",
            "evaluation_metric": "vo2max",
            "metric_kind": "estimated_vo2max",
            "value": 49.073,
            "unit": "mL/kg/min",
            "timestamp": "2026-08-22T19:30:00+00:00",
            "source_type": "fitness_test",
            "source_id": "fitness_test:running_cooper_12min",
            "sources": ["fitness_test:running_cooper_12min"],
            "test_id": "running_cooper_12min",
            "test_result_id": "running_cooper_12min@2026-08-22T19:30:00+00:00",
            "method": "estimated",
            "reference": result["reference"],
        }
    ]
    # Publication is derived; the persisted source result remains untouched.
    assert "source_type" not in result
    assert result["metrics"][0]["value"] == 49.073


def test_test_metrics_feed_canonical_sensor_and_evaluation_with_provenance():
    assert "def canonical_wellness_observation" in MANAGER
    assert "def canonical_evaluation_metric_observation" in MANAGER
    assert "def canonical_metric_observation" in MANAGER
    assert "Source type never participates in ranking." in MANAGER
    assert "source quality or vendor priority" in MANAGER
    assert '"standardized_fitness_test_estimate"' in MANAGER
    assert 'history_metric = observation.get("evaluation_metric") or observation.get("metric")' in MANAGER
    assert 'self.manager.canonical_wellness_observation(m)' in SENSOR
    for attribute in (
        '"test_result_id"',
        '"test_result_metric"',
        '"performed_at"',
        '"study_title"',
        '"study_url"',
    ):
        assert attribute in SENSOR

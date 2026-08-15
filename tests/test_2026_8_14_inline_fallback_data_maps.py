import sys
import types
from pathlib import Path

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")

sleep = load_module("custom_components.fitness.providers.sleep", "providers/sleep.py")
workouts = load_module("custom_components.fitness.providers.workouts", "providers/workouts.py")
SleepRecord = sleep.SleepRecord
Workout = workouts.Workout

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DATA = (ROOT / "custom_components/fitness/profile_data.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_data_map_schema_persists_only_inline_fitness_fallback_values():
    assert "DATA_MAP_SCHEMA_VERSION = 3" in PROFILE_DATA
    attrs_block = PROFILE_DATA.split("def routes_to_attributes", 1)[1].split("def routes_from_attributes", 1)[0]
    assert '_route_keeps_inline_value(route)' in attrs_block
    assert 'route.get("source_type") in INLINE_VALUE_SOURCE_TYPES' in PROFILE_DATA
    assert 'attrs[f"{key}_value"] = route["value"]' in attrs_block
    assert '("value", "value")' in PROFILE_DATA
    assert '["method","method"], ["value","value"]' in FRONTEND


def test_sleep_score_is_an_inline_fallback_not_a_mirror():
    block = DASHBOARD.split("def _sleep_source_metrics", 1)[1].split("def _evaluation_source_metrics", 1)[0]
    assert 'source == "fitness_calculated"' in block
    assert '"transform": "inline"' in block
    assert 'derived_sleep_score_method' in block


def test_strength_source_substitutes_are_explicitly_marked():
    for field in ("exercise_count", "total_reps", "volume_kg"):
        assert field in workouts.FITNESS_FALLBACK_FACTUAL_FIELDS
        assert f'workout.field_sources[field_name] = FITNESS_CALCULATED_SOURCE' in MANAGER
    assert 'route["transform"] = "inline"' in DASHBOARD or '"transform": "inline"' in DASHBOARD


def test_native_sleep_score_replaces_older_fitness_fallback():
    fallback = SleepRecord(
        source="sensor.sleep_overview",
        provider_domain="generic",
        start="2026-08-13T22:00:00+00:00",
        end="2026-08-14T06:00:00+00:00",
        duration_s=8 * 3600,
        light_sleep_s=4 * 3600,
        deep_sleep_s=1.5 * 3600,
        rem_sleep_s=2.5 * 3600,
        score=81.0,
        field_sources={"score": "fitness_calculated"},
        provider_values={"fitness": {"derived_sleep_score": 81.0}},
    )
    native = SleepRecord(
        source="sensor.native_sleep_score",
        provider_domain="garmin_connect",
        start="2026-08-13T22:00:00+00:00",
        end="2026-08-14T06:00:00+00:00",
        score=91.0,
        field_sources={"score": "sensor.native_sleep_score"},
    )

    merged = sleep.merge_sleep_records([fallback, native])
    assert merged.score == 91.0
    assert merged.field_sources["score"] == "sensor.native_sleep_score"


def test_real_strength_facts_replace_calculated_fallbacks_on_later_merge():
    fallback = Workout(
        source="sensor.provider_workout",
        provider_domains=["hevy"],
        exercise_count=4,
        total_reps=48,
        volume_kg=4200,
        field_sources={
            "exercise_count": workouts.FITNESS_CALCULATED_SOURCE,
            "total_reps": workouts.FITNESS_CALCULATED_SOURCE,
            "volume_kg": workouts.FITNESS_CALCULATED_SOURCE,
        },
    )
    native = Workout(
        source="sensor.hevy_last_workout",
        provider_domains=["hevy"],
        exercise_count=5,
        total_reps=52,
        volume_kg=4500,
        field_sources={
            "exercise_count": "hevy",
            "total_reps": "hevy",
            "volume_kg": "hevy",
        },
    )

    merged = workouts.merge_workouts([fallback, native])
    assert merged.exercise_count == 5
    assert merged.total_reps == 52
    assert merged.volume_kg == 4500
    assert merged.field_sources["exercise_count"] == "hevy"
    assert merged.field_sources["total_reps"] == "hevy"
    assert merged.field_sources["volume_kg"] == "hevy"


def test_calculated_strength_fallback_cannot_replace_existing_native_fact():
    native = Workout(
        source="sensor.hevy_last_workout",
        provider_domains=["hevy"],
        exercise_count=5,
        field_sources={"exercise_count": "hevy"},
    )
    fallback = Workout(
        source="sensor.provider_workout",
        provider_domains=["hevy"],
        exercise_count=4,
        field_sources={"exercise_count": workouts.FITNESS_CALCULATED_SOURCE},
    )

    merged = workouts.merge_workouts([native, fallback])
    assert merged.exercise_count == 5
    assert merged.field_sources["exercise_count"] == "hevy"

from pathlib import Path
import importlib.util
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"

# Lightweight HA stubs for unit-loading the provider normalizer.
ha = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
helpers = types.ModuleType("homeassistant.helpers")
er = types.ModuleType("homeassistant.helpers.entity_registry")
er.async_get = lambda hass: None
helpers.entity_registry = er
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.entity_registry", er)

pkg = types.ModuleType("custom_components")
pkg.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", pkg)
fitness_pkg = types.ModuleType("custom_components.fitness")
fitness_pkg.__path__ = [str(FITNESS)]
sys.modules.setdefault("custom_components.fitness", fitness_pkg)
providers_pkg = types.ModuleType("custom_components.fitness.providers")
providers_pkg.__path__ = [str(FITNESS / "providers")]
sys.modules.setdefault("custom_components.fitness.providers", providers_pkg)

spec = importlib.util.spec_from_file_location(
    "custom_components.fitness.providers.workouts",
    FITNESS / "providers" / "workouts.py",
)
workouts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = workouts
spec.loader.exec_module(workouts)


def test_confirmed_session_rpe_provider_capabilities_are_conservative():
    assert workouts.session_rpe_provider_capability("garmin_connect") == "user_session_rpe_1_10"
    assert workouts.session_rpe_provider_capability("polar") == "user_session_rpe_1_10"
    # Do not reinterpret algorithmic strain, Suunto feeling, or Hevy per-set RPE
    # as a workout-level subjective session RPE.
    for provider in ("whoop", "suunto", "hevy", "oura", "fitbit", "peloton", "withings", "strava"):
        assert workouts.session_rpe_provider_capability(provider) is None


def test_garmin_direct_workout_rpe_100_scale_normalizes_to_integer_1_10():
    raw = {
        "activityName": "Run",
        "activityType": "running",
        "startTime": "2026-08-12T10:00:00+00:00",
        "duration": 1800,
        "directWorkoutRpe": 70,
    }
    w = workouts._extract_record(raw, source="sensor.garmin", provider_domain="garmin_connect")
    assert w is not None
    assert w.session_rpe == 7
    assert w.extra["fitness_rpe"]["active_source"] == "provider"
    assert w.extra["fitness_rpe"]["provider"] == "garmin_connect"


def test_garmin_nested_self_evaluation_is_supported():
    raw = {
        "activityName": "Run",
        "startTime": "2026-08-12T10:00:00+00:00",
        "duration": 1800,
        "selfEvaluation": {"perceivedEffort": 8},
    }
    w = workouts._extract_record(raw, source="sensor.garmin", provider_domain="garmin_connect")
    assert w is not None
    assert w.session_rpe == 8


def test_non_rpe_scores_are_not_reinterpreted_as_rpe():
    raw = {
        "activityName": "Workout",
        "startTime": "2026-08-12T10:00:00+00:00",
        "duration": 1800,
        "strain": 17.2,
        "aerobicTrainingEffect": 4.5,
        "feeling": 5,
    }
    w = workouts._extract_record(raw, source="sensor.provider", provider_domain="whoop")
    assert w is not None
    assert w.session_rpe is None


def test_polar_adapter_uses_training_load_pro_rpe_not_cardio_load():
    polar = (FITNESS / "providers" / "workout_adapters" / "polar.py").read_text(encoding="utf-8")
    assert 'training_load_pro' in polar
    assert 'user-rpe' in polar
    assert 'perceived-load' in polar
    assert 'perceived / (duration_s / 60.0)' in polar


def test_user_override_preserves_provider_baseline_and_recalculates():
    manager = (FITNESS / "manager.py").read_text(encoding="utf-8")
    assert 'provider_base_rpe' in manager
    assert 'active_source"] = "user_override"' in manager
    assert 'user_override_rpe' in manager
    assert 'updated=self._apply_beta2_workout_metrics(updated)' in manager
    assert 'await self._async_refresh_long_term_statistics()' in manager


def test_merge_preserves_canonical_provider_rpe_provenance():
    a = workouts._extract_record(
        {
            "activityName": "Run",
            "startTime": "2026-08-12T10:00:00+00:00",
            "duration": 1800,
            "directWorkoutRpe": 70,
        },
        source="sensor.garmin",
        provider_domain="garmin_connect",
    )
    b = workouts._extract_record(
        {
            "name": "Run",
            "start": "2026-08-12T10:00:10+00:00",
            "duration": 1800,
            "distance": 5000,
        },
        source="sensor.other",
        provider_domain="other",
    )
    merged = workouts.merge_workouts([a, b])
    assert merged.session_rpe == 7
    assert merged.extra["fitness_rpe"]["provider"] == "garmin_connect"
    assert merged.extra["fitness_rpe"]["active_source"] == "provider"


def test_live_capture_merges_with_authoritative_provider_sport():
    live = workouts.Workout(
        source="fitness_live_capture",
        name="Evening Ride – 2026-08-12 19:39",
        sport="ride",
        start="2026-08-12T17:39:11+00:00",
        end="2026-08-12T18:15:59+00:00",
        duration_s=2208,
        avg_hr=120,
        max_hr=151,
        hrr_60s=53,
        hrr_120s=59,
        session_rpe=6,
    )
    garmin = workouts.Workout(
        source="sensor.last_activities",
        name="Ενδυνάμωση",
        sport="strength",
        start="2026-08-12T17:40:05+00:00",
        end="2026-08-12T18:16:00+00:00",
        duration_s=2155,
        avg_hr=120,
        max_hr=151,
        total_reps=257,
        provider_domains=["garmin_connect"],
    )
    merged = workouts.merged_workouts([live, garmin])
    assert len(merged) == 1
    item = merged[0]
    assert item.sport == "strength"
    assert item.name == "Ενδυνάμωση"
    assert item.hrr_60s == 53
    assert item.hrr_120s == 59
    assert item.total_reps == 257
    assert item.session_rpe == 6

import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault(
    "custom_components.fitness",
    types.ModuleType("custom_components.fitness"),
)
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers",
    types.ModuleType("custom_components.fitness.providers"),
)
providers_pkg.__path__ = [str(FITNESS / "providers")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")

workouts = load_module(
    "custom_components.fitness.providers.workouts",
    "providers/workouts.py",
)


def test_polar_style_mapping_preserves_provider_fields():
    workout = workouts._extract_record(
        {
            "name": "RUNNING",
            "sport": "RUNNING",
            "start": "2026-08-09T10:00:00+00:00",
            "duration_s": 3600,
            "distance_m": 10000,
            "avg_hr": 150,
            "max_hr": 180,
            "calories": 700,
            "training_load": 95,
            "running_index": 55,
            "device_name": "Polar Vantage",
        },
        source="sensor.polar_last_exercise",
        provider_domain="polar",
    )
    assert workout is not None
    assert workout.sport == "RUNNING"
    assert workout.duration_s == 3600
    assert workout.avg_hr == 150
    assert workout.max_hr == 180
    assert workout.extra["running_index"] == 55
    assert workout.provider_values["polar"]["training_load"] == 95


def test_provider_fields_can_enrich_same_workout():
    garmin = workouts._extract_record(
        {
            "activityName": "Morning Run",
            "activityType": "running",
            "startTime": "2026-08-09T10:00:00+00:00",
            "duration": 3600,
            "distance": 10000,
            "averageHR": 150,
        },
        source="sensor.garmin_connect_last_activity",
        provider_domain="garmin_connect",
    )
    polar = workouts._extract_record(
        {
            "name": "Running",
            "sport": "running",
            "start": "2026-08-09T10:00:10+00:00",
            "duration_s": 3598,
            "distance_m": 9990,
            "training_load": 95,
            "running_index": 55,
        },
        source="sensor.polar_last_exercise",
        provider_domain="polar",
    )

    merged = workouts.merged_workouts([garmin, polar])
    assert len(merged) == 1
    assert set(merged[0].provider_domains) == {"garmin_connect", "polar"}
    assert merged[0].avg_hr == 150
    assert any(
        key.endswith("running_index")
        for key in merged[0].extra
    )

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


def _mirror_block() -> str:
    start = SENSOR.index("WORKOUT_SOURCE_MIRROR_KEYS = frozenset({")
    end = SENSOR.index("\n})", start) + 3
    return SENSOR[start:end]


def test_completed_workout_source_fields_are_not_fitness_entities():
    mirrors = _mirror_block()
    for key in (
        "last_workout",
        "last_workout_duration",
        "last_workout_distance",
        "last_workout_avg_hr",
        "last_workout_avg_power",
        "last_workout_vo2max",
        "last_workout_training_load",
        "last_workout_device",
        "last_workout_sources",
    ):
        assert f'"{key}"' in mirrors

    assert "desc.key not in WORKOUT_SOURCE_MIRROR_KEYS" in SENSOR
    assert "if key in WORKOUT_SOURCE_MIRROR_KEYS:" in SENSOR
    assert "registry.async_remove(registry_entry.entity_id)" in SENSOR


def test_fitness_derived_workout_entities_remain_materialized():
    mirrors = _mirror_block()
    for key in (
        "last_workout_banister_trimp",
        "last_workout_aerobic_efficiency",
        "last_workout_aerobic_decoupling",
        "last_workout_session_rpe_load",
        "last_workout_efficiency_vs_baseline",
        "last_workout_estimated_1rm",
    ):
        assert f'"{key}"' not in mirrors
        assert f'Desc(key="{key}"' in SENSOR


def test_dashboard_routes_factual_metrics_to_upstream_entities():
    assert '"workout_source_metrics": workout_source_metrics' in DASHBOARD
    assert "def _workout_source_metrics(" in DASHBOARD
    assert "if registry_entry.platform == DOMAIN:" in DASHBOARD
    assert '"entity_id": registry_entry.entity_id' in DASHBOARD
    assert '"attribute": str(attr_name)' in DASHBOARD
    assert '"transform": "state"' in DASHBOARD


def test_frontend_uses_source_routes_for_factual_workout_values():
    assert "const _fitnessWorkoutSourceMetric = (" in FRONTEND
    assert "const _fitnessWorkoutSourceSignature = (" in FRONTEND
    assert "const sourceKeys = [" in FRONTEND
    assert "const fitnessKeys = [" in FRONTEND

    # Raw/factual workout values must not be read from mirrored Fitness entities.
    for expression in (
        "e.last_workout_distance",
        "e.last_workout_duration",
        "e.last_workout_avg_hr",
        "e.last_workout_max_hr",
        "e.last_workout_avg_power",
        "e.last_workout_avg_cadence",
        "e.last_workout_vo2max",
        "e.last_workout_calories",
    ):
        assert expression not in FRONTEND

    # Derived Fitness values remain legitimate Fitness entities.
    assert "e.last_workout_session_rpe_load" in FRONTEND
    assert "e.last_workout_strength_sets" in FRONTEND


def test_dashboard_resource_version_matches_frontend_after_routing_change():
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.3"' in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.11.3"' in FRONTEND

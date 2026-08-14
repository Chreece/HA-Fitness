from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


def _fitness_owned_fact_block() -> str:
    start = SENSOR.index("FITNESS_OWNED_WORKOUT_FACT_FIELDS = {")
    end = SENSOR.index("\n}\n\nFITNESS_OWNED_WORKOUT_FACT_KEYS", start) + 2
    return SENSOR[start:end]


def test_completed_workout_facts_exist_only_for_fitness_owned_workouts():
    facts = _fitness_owned_fact_block()
    for key in (
        "last_workout",
        "last_workout_duration",
        "last_workout_distance",
        "last_workout_avg_hr",
        "last_workout_avg_power",
        "last_workout_vo2max",
        "last_workout_training_load",
        "last_workout_device",
    ):
        assert f'"{key}"' in facts

    # Pure provider workout facts are never exposed by these entities: the
    # entity value path explicitly switches to latest_fitness_workout() and
    # extracts only the Fitness-owned field value.
    assert "if key in FITNESS_OWNED_WORKOUT_FACT_KEYS:" in SENSOR
    assert "w = self.manager.latest_fitness_workout()" in SENSOR
    assert "fitness_owned_workout_value(w, field_name)" in SENSOR

    # Sleep remains a strict external-source mirror exclusion.
    assert "SOURCE_MIRROR_KEYS = SLEEP_SOURCE_MIRROR_KEYS" in SENSOR


def test_fitness_derived_workout_entities_remain_materialized():
    facts = _fitness_owned_fact_block()
    for key in (
        "last_workout_banister_trimp",
        "last_workout_aerobic_efficiency",
        "last_workout_aerobic_decoupling",
        "last_workout_session_rpe_load",
        "last_workout_efficiency_vs_baseline",
        "last_workout_estimated_1rm",
    ):
        assert f'"{key}"' not in facts
        assert f'Desc(key="{key}"' in SENSOR


def test_dashboard_routes_external_fields_to_sources_and_fitness_fields_to_fitness():
    assert '"workout_source_metrics": workout_source_metrics' in DASHBOARD
    assert "def _workout_source_metrics(" in DASHBOARD
    assert "if registry_entry.platform == DOMAIN:" in DASHBOARD
    assert '"entity_id": registry_entry.entity_id' in DASHBOARD
    assert '"attribute": str(attr_name)' in DASHBOARD
    assert '"transform": "state"' in DASHBOARD
    assert "workout_is_fitness_owned(workout) and provider == FITNESS_LIVE_SOURCE" in DASHBOARD
    assert '"source_type": "fitness_owned"' in DASHBOARD


def test_frontend_uses_source_routes_for_factual_workout_values():
    assert "const _fitnessWorkoutSourceMetric = (" in FRONTEND
    assert "const _fitnessWorkoutSourceSignature = (" in FRONTEND
    assert "const sourceKeys = [" in FRONTEND
    assert "const fitnessKeys = [" in FRONTEND

    # Dashboard factual values go through the route table; direct Fitness
    # entity access is reserved for the calculated entity list.
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

    assert "e.last_workout_session_rpe_load" in FRONTEND
    assert "e.last_workout_strength_sets" in FRONTEND


def test_dashboard_resource_version_matches_frontend_after_owned_workout_routing_change():
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.6"' in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.11.6"' in FRONTEND

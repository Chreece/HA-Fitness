import sys
import types
from pathlib import Path

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

custom = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
custom.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]
workout_adapters_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.workout_adapters",
    types.ModuleType("custom_components.fitness.providers.workout_adapters"),
)
workout_adapters_pkg.__path__ = [str(FITNESS / "providers" / "workout_adapters")]
sleep_adapters_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.sleep_adapters",
    types.ModuleType("custom_components.fitness.providers.sleep_adapters"),
)
sleep_adapters_pkg.__path__ = [str(FITNESS / "providers" / "sleep_adapters")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")
workouts = sys.modules.get("custom_components.fitness.providers.workouts") or load_module(
    "custom_components.fitness.providers.workouts", "providers/workouts.py"
)
sleep = sys.modules.get("custom_components.fitness.providers.sleep") or load_module(
    "custom_components.fitness.providers.sleep", "providers/sleep.py"
)
load_module(
    "custom_components.fitness.providers.workout_adapters.base",
    "providers/workout_adapters/base.py",
)
polar = load_module(
    "custom_components.fitness.providers.workout_adapters.polar",
    "providers/workout_adapters/polar.py",
)
load_module(
    "custom_components.fitness.providers.sleep_adapters.registry_types",
    "providers/sleep_adapters/registry_types.py",
)
sleep_as_android = load_module(
    "custom_components.fitness.providers.sleep_adapters.sleep_as_android",
    "providers/sleep_adapters/sleep_as_android.py",
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DATA = (ROOT / "custom_components/fitness/profile_data.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_inline_map_contract_is_narrow_and_explicit():
    assert 'DATA_MAP_SCHEMA_VERSION = 3' in PROFILE_DATA
    for source_type in ("fitness_calculated", "source_reconstructed", "source_normalized"):
        assert f'"{source_type}"' in PROFILE_DATA
    assert 'route.get("source_type") in INLINE_VALUE_SOURCE_TYPES' in PROFILE_DATA
    assert 'attrs[f"{key}_value"] = route["value"]' in PROFILE_DATA


def test_sleep_as_android_marks_exact_recorder_reconstructions():
    from datetime import datetime, timezone

    class EventState:
        def __init__(self, stamp, event_type):
            self.last_updated = stamp
            self.last_changed = stamp
            self.attributes = {"event_type": event_type}

    def dt(hour, minute=0):
        return datetime(2026, 8, 13, hour, minute, tzinfo=timezone.utc)

    tracking = [
        EventState(dt(22), "started"),
        EventState(datetime(2026, 8, 14, 6, 0, tzinfo=timezone.utc), "stopped"),
    ]
    phases = [
        EventState(dt(22), "light_sleep"),
        EventState(dt(23), "deep_sleep"),
        EventState(datetime(2026, 8, 14, 0, 30, tzinfo=timezone.utc), "light_sleep"),
        EventState(datetime(2026, 8, 14, 4, 30, tzinfo=timezone.utc), "rem"),
    ]
    records = sleep_as_android.records_from_event_history(
        tracking_entity_id="event.sleep_tracking",
        phase_entity_id="event.sleep_phase",
        tracking_states=tracking,
        phase_states=phases,
    )
    assert len(records) == 1
    meta = records[0].provider_values["sleep_as_android"]
    assert meta["stage_method"] == "home_assistant_recorder_event_timeline"
    assert "duration_s" in meta["reconstructed_fields"]
    assert "light_sleep_s" in meta["reconstructed_fields"]
    assert "deep_sleep_s" in meta["reconstructed_fields"]
    assert "rem_sleep_s" in meta["reconstructed_fields"]


def test_impossible_sleep_duration_is_marked_as_normalized_fallback():
    record = sleep.SleepRecord(
        source="sensor.sleep",
        provider_domain="provider",
        start="2026-08-13T22:00:00+00:00",
        end="2026-08-14T06:00:00+00:00",
        duration_s=6 * 3600,
        light_sleep_s=4 * 3600,
        deep_sleep_s=90 * 60,
        rem_sleep_s=90 * 60,
        field_sources={
            "duration_s": "sensor.sleep_duration",
            "light_sleep_s": "sensor.sleep_light",
            "deep_sleep_s": "sensor.sleep_deep",
            "rem_sleep_s": "sensor.sleep_rem",
        },
        sources=["sensor.sleep_duration", "sensor.sleep_light", "sensor.sleep_deep", "sensor.sleep_rem"],
        provider_domains=["provider"],
    )
    merged = sleep.merge_sleep_records([record])
    assert merged.duration_s == 7 * 3600
    assert merged.field_sources["duration_s"] == "provider:classified_sleep_stages"
    assert merged.provider_values["fitness"]["normalized_sleep_duration_method"] == (
        "max_provider_duration_and_classified_sleep_stages"
    )


def test_polar_exact_rpe_reconstruction_is_provisional_and_native_can_replace_it():
    attrs = {"training_load_pro": {"perceived_load": 420}}
    value, method = polar._polar_session_rpe_details(attrs, 60 * 60)
    assert value == 7
    assert method == "polar_perceived_load_div_duration_minutes"

    fallback = workouts.Workout(
        source="sensor.polar_last_exercise",
        provider_domains=["polar"],
        session_rpe=7,
        field_sources={"session_rpe": workouts.SOURCE_RECONSTRUCTED_SOURCE},
        provider_values={"polar": {"derived_session_rpe_method": method}},
    )
    native = workouts.Workout(
        source="sensor.polar_last_exercise",
        provider_domains=["polar"],
        session_rpe=8,
        field_sources={"session_rpe": "polar"},
    )
    merged = workouts.merge_workouts([fallback, native])
    assert merged.session_rpe == 8
    assert merged.field_sources["session_rpe"] == "polar"


def test_dashboard_routes_reconstructed_facts_inline_and_unit_conversions_to_sources():
    sleep_block = DASHBOARD.split("def _sleep_source_metrics", 1)[1].split(
        "def _evaluation_source_metrics", 1
    )[0]
    workout_block = DASHBOARD.split("def _workout_source_metrics", 1)[1].split(
        "def _route_matches_latest_workout", 1
    )[0]
    assert '"source_type": "source_reconstructed"' in sleep_block
    assert '"source_type": "source_normalized"' in sleep_block
    assert 'SOURCE_RECONSTRUCTED_SOURCE' in workout_block
    assert '"transform": "wh_to_kj"' in workout_block
    assert 'return "rpe_0_100_to_1_10"' in DASHBOARD
    assert 'route.transform === "wh_to_kj"' in FRONTEND
    assert 'route.transform === "rpe_0_100_to_1_10"' in FRONTEND


def test_genuine_fitness_formula_entities_are_not_folded_into_inline_fallbacks():
    # These remain normal Fitness-owned entities/routes. The inline audit is
    # deliberately limited to substitute source facts.
    for key in (
        "readiness", "estimated_recovery_time", "sleep_deficit_7d",
        "autonomic_recovery_trend", "cardiorespiratory_fitness_trend",
        "vo2max_percent_predicted", "training_load", "heart_rate_recovery",
        "training_recovery_relationship", "training_adaptation_status",
    ):
        assert f'Desc(key="{key}"' in (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")

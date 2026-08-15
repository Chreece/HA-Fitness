from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

# The provider modules use normal package-relative imports. Supply lightweight
# package shells like the rest of the adapter unit tests do.
pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault(
    "custom_components.fitness", types.ModuleType("custom_components.fitness")
)
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers")
)
providers_pkg.__path__ = [str(FITNESS / "providers")]
sleep_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.sleep_adapters",
    types.ModuleType("custom_components.fitness.providers.sleep_adapters"),
)
sleep_pkg.__path__ = [str(FITNESS / "providers" / "sleep_adapters")]
workout_pkg = sys.modules.setdefault(
    "custom_components.fitness.providers.workout_adapters",
    types.ModuleType("custom_components.fitness.providers.workout_adapters"),
)
workout_pkg.__path__ = [str(FITNESS / "providers" / "workout_adapters")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")
sleep = load_module("custom_components.fitness.providers.sleep", "providers/sleep.py")
load_module(
    "custom_components.fitness.providers.sleep_adapters.registry_types",
    "providers/sleep_adapters/registry_types.py",
)
healthsync_sleep = load_module(
    "custom_components.fitness.providers.sleep_adapters.healthsync",
    "providers/sleep_adapters/healthsync.py",
)
workouts = load_module(
    "custom_components.fitness.providers.workouts", "providers/workouts.py"
)
base = load_module(
    "custom_components.fitness.providers.workout_adapters.base",
    "providers/workout_adapters/base.py",
)
healthsync_workouts = load_module(
    "custom_components.fitness.providers.workout_adapters.healthsync",
    "providers/workout_adapters/healthsync.py",
)


class _States:
    def __init__(self, values):
        self._values = values

    def get(self, entity_id):
        return self._values.get(entity_id)


def _state(value, *, attrs=None, updated=None):
    return SimpleNamespace(
        state=str(value),
        attributes=dict(attrs or {}),
        last_updated=updated or datetime(2026, 8, 14, 6, 30, tzinfo=timezone.utc),
    )


def _entry(entity_id, unique_id, name):
    return SimpleNamespace(
        entity_id=entity_id,
        unique_id=unique_id,
        name=name,
        original_name=name,
        translation_key=None,
        device_id="healthsync-device",
        config_entry_id="healthsync-entry",
    )


def test_healthsync_sleep_snapshot_parses_stage_attributes_and_timestamps():
    entries = [
        _entry("sensor.healthsync_sleep_last_night", "abc_sleep_duration", "Sleep last night"),
        _entry("sensor.healthsync_fell_asleep", "abc_sleep_onset", "Fell asleep"),
        _entry("sensor.healthsync_woke_up", "abc_sleep_wake", "Woke up"),
    ]
    hass = SimpleNamespace(states=_States({
        "sensor.healthsync_sleep_last_night": _state(
            7.5,
            attrs={
                "unit_of_measurement": "h",
                "deep_minutes": 90,
                "rem_minutes": 105,
                "core_minutes": 240,
                "awake_minutes": 15,
            },
        ),
        "sensor.healthsync_fell_asleep": _state(
            "22:45", attrs={"timestamp": "2026-08-13T20:45:00+00:00"}
        ),
        "sensor.healthsync_woke_up": _state(
            "06:30", attrs={"timestamp": "2026-08-14T04:30:00+00:00"}
        ),
    }))

    record = healthsync_sleep.discover(hass, entries)
    assert record is not None
    assert record.duration_s == 7.5 * 3600
    assert record.light_sleep_s == 240 * 60
    assert record.deep_sleep_s == 90 * 60
    assert record.rem_sleep_s == 105 * 60
    assert record.awake_s == 15 * 60
    assert record.start == "2026-08-13T20:45:00+00:00"
    assert record.end == "2026-08-14T04:30:00+00:00"
    route = record.provider_values["healthsync"]["field_routes"]["deep_sleep_s"]
    assert route == {
        "entity_id": "sensor.healthsync_sleep_last_night",
        "attribute": "deep_minutes",
        "transform": "identity",
        "unit": "min",
    }

    # HealthSync has no native sleep-score scalar; Fitness may transparently
    # calculate its existing fallback from the complete stage bundle.
    merged = sleep.merged_sleeps([record])[0]
    assert merged.score is not None
    assert merged.field_sources["score"] == "fitness_calculated"


def test_healthsync_recent_workout_slots_are_first_class_workouts(monkeypatch):
    slot0 = _entry(
        "sensor.healthsync_functional_strength_training",
        "abc_workout_slot_0",
        "Functional Strength Training",
    )
    slot1 = _entry(
        "sensor.healthsync_running",
        "abc_workout_slot_1",
        "Running",
    )
    hass = SimpleNamespace(states=_States({
        slot0.entity_id: _state(
            "functionalStrengthTraining",
            attrs={
                "started_at": "2026-08-14T17:00:00+00:00",
                "ended_at": "2026-08-14T17:45:00+00:00",
                "duration_min": 45,
                "distance_m": None,
                "calories": 320,
            },
        ),
        slot1.entity_id: _state(
            "running",
            attrs={
                "started_at": "2026-08-13T17:00:00+00:00",
                "ended_at": "2026-08-13T17:30:00+00:00",
                "duration_min": 30,
                "distance_m": 5000,
                "calories": 280,
            },
        ),
    }))
    monkeypatch.setattr(
        healthsync_workouts,
        "selected_device_entries_by_domain",
        lambda *_args, **_kwargs: {"healthsync-device": [slot0, slot1]},
    )

    found = healthsync_workouts.discover(hass, {})
    assert len(found) == 2
    newest = found[0]
    assert newest.source == slot0.entity_id
    assert newest.duration_s == 45 * 60
    assert newest.calories == 320
    assert workouts._sport_key(newest.sport) == "strength"
    assert workouts._sport_key("traditionalStrengthTraining") == "strength"
    assert workouts._sport_key("highIntensityIntervalTraining") == "hiit"


def test_healthsync_normalizer_accepts_slot_contract_keys():
    workout = workouts._extract_record(
        {
            "workout_type": "running",
            "started_at": "2026-08-14T18:00:00+00:00",
            "ended_at": "2026-08-14T18:42:00+00:00",
            "duration_min": 42,
            "distance_m": 7000,
            "calories": 410,
        },
        source="sensor.healthsync_slot_0",
        provider_domain="healthsync",
    )
    assert workout is not None
    assert workout.duration_s == 2520
    assert workout.distance_m == 7000
    assert workout.calories == 410



def test_healthsync_strength_merges_with_fitness_live_capture():
    live = workouts.Workout(
        source=workouts.FITNESS_LIVE_SOURCE,
        sources=[workouts.FITNESS_LIVE_SOURCE],
        name="Strength workout",
        sport="strength",
        start="2026-08-14T17:00:20+00:00",
        end="2026-08-14T17:45:00+00:00",
        duration_s=2680,
        avg_hr=121,
        sample_count=100,
    )
    apple = workouts._extract_record(
        {
            "workout_type": "functionalStrengthTraining",
            "started_at": "2026-08-14T17:00:00+00:00",
            "ended_at": "2026-08-14T17:45:00+00:00",
            "duration_min": 45,
            "calories": 320,
        },
        source="sensor.healthsync_strength",
        provider_domain="healthsync",
    )
    merged = workouts.merged_workouts([live, apple])
    assert len(merged) == 1
    assert workouts.workout_is_fitness_owned(merged[0])
    assert workouts._sport_key(merged[0].sport) == "strength"
    assert merged[0].calories == 320
    assert "healthsync" in merged[0].provider_domains

def test_healthsync_integration_hooks_and_dashboard_routes_exist():
    root = Path(__file__).resolve().parents[1]
    history = (root / "custom_components/fitness/providers/workout_history.py").read_text()
    evaluation = (root / "custom_components/fitness/providers/evaluation.py").read_text()
    dashboard = (root / "custom_components/fitness/dashboard.py").read_text()
    frontend = (root / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()

    assert '"healthsync", "get_readings"' in history
    assert 'service_data = {"device_id": device_id, "metric": "workouts"}' in history
    assert 'service_data["start"] = history_start' in history
    assert '"_workout_slot_" in unique_id' in evaluation
    assert 'healthsync_routes = healthsync_values.get("field_routes")' in dashboard
    assert 'route.attribute && state' in frontend

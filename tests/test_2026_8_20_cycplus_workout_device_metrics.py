from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()
components = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
components.__path__ = []
sys.modules.setdefault("homeassistant.components.bluetooth", types.ModuleType("homeassistant.components.bluetooth"))
storage = sys.modules.setdefault("homeassistant.helpers.storage", types.ModuleType("homeassistant.helpers.storage"))

class _Store:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls

storage.Store = _Store
root_pkg = sys.modules.setdefault("cycplus_metrics_test", types.ModuleType("cycplus_metrics_test"))
root_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("cycplus_metrics_test.providers", types.ModuleType("cycplus_metrics_test.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]
adapters_pkg = sys.modules.setdefault("cycplus_metrics_test.device_adapters", types.ModuleType("cycplus_metrics_test.device_adapters"))
adapters_pkg.__path__ = [str(FITNESS / "device_adapters")]
load_module("cycplus_metrics_test.const", "const.py")
load_module("cycplus_metrics_test.providers.workouts", "providers/workouts.py")
cycplus = load_module("cycplus_metrics_test.device_adapters.cycplus_m1", "device_adapters/cycplus_m1.py")


ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"


def test_m1_duplicate_enhanced_speed_fields_do_not_mask_scalar_speed_aliases():
    start = datetime(2026, 8, 14, 9, 36, 25, tzinfo=timezone.utc)
    end = datetime(2026, 8, 14, 9, 50, 4, tzinfo=timezone.utc)
    messages = [
        (
            "session",
            {
                "start_time": start,
                "timestamp": end,
                "sport": "cycling",
                "total_timer_time": 819.0,
                "total_moving_time": 819.0,
                "total_elapsed_time": 819.0,
                "total_distance": 4811.95,
                # This is what the user's real M1 FIT payload normalized to:
                # fitdecode retained duplicate enhanced fields as a list while
                # the legacy scalar alias was also present.
                "enhanced_avg_speed": [5.882, 5.882],
                "avg_speed": 5.882,
                "enhanced_max_speed": [8.507, 8.507],
                "max_speed": 8.507,
                "num_laps": 1,
            },
        )
    ]

    result = cycplus.workouts_from_fit_messages(
        messages,
        filename="20260814093625.fit",
        sensor_id="sensor:test",
        advertised_number="98C6",
        sha256="sample",
    )

    workout = result.workouts[0]
    assert workout.average_speed_m_s == 5.882
    assert workout.max_speed_m_s == 8.507
    assert workout.moving_time_s == 819.0


def test_m1_device_workout_metrics_match_real_archive_shape_and_are_conditional():
    workouts = [
        {
            "source": "cycplus_m1:one",
            "start": "2026-08-14T09:36:25+00:00",
            "duration_s": 819.0,
            "moving_time_s": 819.0,
            "elapsed_time_s": 239597.0,
            "distance_m": 4811.95,
            "elevation_gain_m": 13.0,
            "elevation_loss_m": 13.0,
            "average_speed_m_s": None,
            "max_speed_m_s": None,
            "avg_hr": None,
            "avg_power": None,
            "avg_cadence": None,
            "provider_values": {
                "cycplus_m1": {
                    "avg_altitude": 67.0,
                    "avg_neg_grade": -1.01,
                    "avg_pos_grade": 1.05,
                    "avg_speed": 5.882,
                    "avg_temperature": 31,
                    "enhanced_avg_speed": [5.882, 5.882],
                    "max_altitude": 73.4,
                    "max_neg_grade": -2.68,
                    "max_pos_grade": 3.42,
                    "max_speed": 8.507,
                    "max_temperature": 37,
                    "min_altitude": 63.2,
                    "total_ascent": 13,
                    "total_descent": 13,
                    "total_distance": 4811.95,
                    "total_moving_time": 819.0,
                    "total_timer_time": 819.0,
                }
            },
        },
        {
            "source": "cycplus_m1:two",
            "start": "2026-08-14T04:13:39+00:00",
            "duration_s": 773.0,
            "moving_time_s": 773.0,
            "distance_m": 4713.89,
            "elevation_gain_m": 9.0,
            "provider_values": {"cycplus_m1": {"avg_speed": 6.106, "max_speed": 8.785}},
        },
        {
            "source": "cycplus_m1:three",
            "start": "2026-08-13T13:20:44+00:00",
            "duration_s": 904.0,
            "moving_time_s": 904.0,
            "distance_m": 4786.91,
            "elevation_gain_m": 9.0,
            "provider_values": {"cycplus_m1": {"avg_speed": 5.301, "max_speed": 8.008}},
        },
    ]
    state = {
        "files": {
            f"2026081{index}000000.fit": {"workouts": [workout]}
            for index, workout in enumerate(workouts, 1)
        }
    }

    values = cycplus._cycplus_workout_metrics(
        state, now=datetime(2026, 8, 20, 19, 36, tzinfo=timezone.utc)
    )

    assert values["cycplus_history_workout_count"] == 3
    assert values["cycplus_workout_duration"] == 13.65
    assert values["cycplus_workout_distance"] == 4.812
    assert values["cycplus_workout_average_speed"] == 21.18
    assert values["cycplus_workout_max_speed"] == 30.63
    assert values["cycplus_workout_elevation_gain"] == 13
    assert values["cycplus_workout_elevation_loss"] == 13
    assert values["cycplus_workout_avg_altitude"] == 67
    assert values["cycplus_workout_max_altitude"] == 73.4
    assert values["cycplus_workout_min_altitude"] == 63.2
    assert values["cycplus_workout_avg_temperature"] == 31
    assert values["cycplus_workout_max_temperature"] == 37
    assert values["cycplus_workout_avg_positive_grade"] == 1.05
    assert values["cycplus_workout_max_positive_grade"] == 3.42
    assert values["cycplus_workout_avg_negative_grade"] == -1.01
    assert values["cycplus_workout_max_negative_grade"] == -2.68
    assert values["cycplus_history_total_distance"] == 14.31
    assert values["cycplus_history_total_moving_time"] == 0.69
    assert values["cycplus_history_total_ascent"] == 31
    assert values["cycplus_history_7d_distance"] == 9.53
    assert values["cycplus_history_7d_moving_time"] == 0.44
    assert values["cycplus_history_30d_distance"] == 14.31
    assert values["cycplus_history_30d_moving_time"] == 0.69

    # The user's supplied latest rides contain no HR/cadence/power. Those
    # entities must not be materialized just because the model can support them.
    assert "cycplus_workout_avg_hr" not in values
    assert "cycplus_workout_avg_cadence" not in values
    assert "cycplus_workout_avg_power" not in values


def test_m1_optional_sensor_metrics_appear_when_the_latest_fit_workout_has_them():
    state = {
        "files": {
            "20260819120000.fit": {
                "workouts": [
                    {
                        "source": "cycplus_m1:metric-rich",
                        "start": "2026-08-19T12:00:00+00:00",
                        "duration_s": 3600,
                        "moving_time_s": 3500,
                        "distance_m": 30000,
                        "avg_hr": 148,
                        "max_hr": 176,
                        "avg_power": 221,
                        "max_power": 612,
                        "weighted_power": 244,
                        "avg_cadence": 88,
                        "max_cadence": 112,
                        "calories": 710,
                        "training_load": 82,
                        "aerobic_training_effect": 3.2,
                        "anaerobic_training_effect": 1.1,
                        "kilojoules": 796,
                        "provider_values": {"cycplus_m1": {"avg_speed": 8.57, "max_speed": 15.2}},
                    }
                ]
            }
        }
    }

    values = cycplus._cycplus_workout_metrics(
        state, now=datetime(2026, 8, 20, tzinfo=timezone.utc)
    )
    assert values["cycplus_workout_avg_hr"] == 148
    assert values["cycplus_workout_max_hr"] == 176
    assert values["cycplus_workout_avg_power"] == 221
    assert values["cycplus_workout_max_power"] == 612
    assert values["cycplus_workout_weighted_power"] == 244
    assert values["cycplus_workout_avg_cadence"] == 88
    assert values["cycplus_workout_max_cadence"] == 112
    assert values["cycplus_workout_calories"] == 710
    assert values["cycplus_workout_training_load"] == 82
    assert values["cycplus_workout_aerobic_effect"] == 3.2
    assert values["cycplus_workout_anaerobic_effect"] == 1.1
    assert values["cycplus_workout_kilojoules"] == 796


def test_m1_workout_entities_are_normal_device_sensors_and_all_translations_exist():
    # Workout/history facts belong in the normal Sensors group, not Diagnostics.
    assert all("entity_category" not in meta for meta in cycplus._WORKOUT_META.values())
    assert "entity_category" not in cycplus._DETAIL_META["cycplus_latest_workout"]

    translation_keys = {
        str(meta["translation_key"])
        for meta in cycplus._WORKOUT_META.values()
        if meta.get("translation_key")
    }
    paths = [FIT / "strings.json", *sorted((FIT / "translations").glob("*.json"))]
    assert len(paths) == 16
    for path in paths:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        assert translation_keys <= set(catalog["entity"]["sensor"]), path.name
    assert (FIT / "strings.json").read_bytes() == (FIT / "translations/en.json").read_bytes()

"""Regression tests for the 2026.8.11 canonical workout calendar."""
from __future__ import annotations

import sys
import types

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
calendar_strings = load_module("custom_components.fitness.calendar_strings", "calendar_strings.py")
workouts = load_module("custom_components.fitness.providers.workouts", "providers/workouts.py")

# calendar.py is a HA platform module, but these unit tests only exercise its
# pure formatting/identity helpers. Stub the tiny HA surface required to load it.
components = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
components.__path__ = []
calendar_stub = types.ModuleType("homeassistant.components.calendar")

class CalendarEntity:
    pass

class CalendarEntityFeature:
    DELETE_EVENT = 1

class CalendarEvent:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

calendar_stub.CalendarEntity = CalendarEntity
calendar_stub.CalendarEntityFeature = CalendarEntityFeature
calendar_stub.CalendarEvent = CalendarEvent
sys.modules["homeassistant.components.calendar"] = calendar_stub

util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
util.__path__ = []
dt_stub = types.ModuleType("homeassistant.util.dt")
dt_stub.as_local = lambda value: value
sys.modules["homeassistant.util.dt"] = dt_stub
util.dt = dt_stub

entity_stub = types.ModuleType("custom_components.fitness.entity")
entity_stub.device_info = lambda entry, group=None: {}
sys.modules["custom_components.fitness.entity"] = entity_stub

calendar = load_module("custom_components.fitness.calendar", "calendar.py")
Workout = workouts.Workout
_extract_record = workouts._extract_record


def test_calendar_uid_is_provider_independent_inside_same_start_bucket():
    garmin = Workout(source="sensor.garmin", sport="running", start="2026-08-13T08:01:12+00:00")
    strava = Workout(source="sensor.strava", sport="running", start="2026-08-13T08:01:44+00:00")
    assert calendar._event_uid("abc", garmin) == calendar._event_uid("abc", strava)


def test_calendar_start_location_from_normalized_gps():
    workout = _extract_record(
        {
            "activityName": "Morning Run",
            "activityType": "running",
            "startTime": "2026-08-13T08:00:00+00:00",
            "startLatitude": 50.1234564,
            "startLongitude": 6.7654321,
            "duration": 1800,
        },
        source="sensor.garmin_last_activity",
        provider_domain="garmin_connect",
    )
    assert workout is not None
    assert workout.start_latitude == 50.1234564
    assert workout.start_longitude == 6.7654321
    assert calendar._location(workout) == "50.123456, 6.765432"


def test_calendar_rejects_invalid_start_location():
    workout = Workout(
        source="test",
        start="2026-08-13T08:00:00+00:00",
        start_latitude=120,
        start_longitude=7,
    )
    assert calendar._location(workout) is None


def test_provider_name_is_preserved_but_generated_sport_is_localized():
    named = Workout(source="test", name="Morning Run", sport="running", start="2026-08-13T08:00:00+00:00")
    unnamed = Workout(source="test", sport="running", start="2026-08-13T08:00:00+00:00")
    assert calendar._summary(named, "de") == "Morning Run"
    assert calendar._summary(unnamed, "de") == "Laufen"
    assert calendar._summary(unnamed, "el") == "Τρέξιμο"


def test_calendar_description_is_compact_and_omits_missing_values():
    workout = Workout(
        source="test",
        sport="running",
        start="2026-08-13T08:00:00+00:00",
        duration_s=1800,
        distance_m=5000,
        avg_hr=150,
    )
    text = calendar._description(workout, "en")
    assert "Duration: 30:00" in text
    assert "Distance: 5.00 km" in text
    assert "Avg HR: 150 bpm" in text
    assert "Avg power" not in text
    assert "TRIMP" not in text


def test_calendar_translation_catalog_matches_supported_languages():
    supported = {"de", "el", "en", "es", "fr", "it", "ja", "ko", "nl", "pl", "pt", "ru", "tr", "uk", "zh"}
    for language in supported:
        assert calendar_strings.normalize_language(language) == language
        assert calendar_strings.tr(language, "workouts")
        assert calendar_strings.tr(language, "details")
    assert calendar_strings.normalize_language("de-DE") == "de"
    assert calendar_strings.normalize_language("xx") == "en"

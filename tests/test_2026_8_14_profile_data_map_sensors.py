from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
PROFILE_DATA = (ROOT / "custom_components/fitness/profile_data.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
CALENDAR = (ROOT / "custom_components/fitness/calendar.py").read_text(encoding="utf-8")


def test_each_profile_device_has_one_stable_data_map_sensor():
    expected = {
        "workout_data": "workout",
        "live_data": "live",
        "recovery_data": "sleep",
        "evaluation_data": "evaluation",
    }
    for key, kind in expected.items():
        assert f'Desc(key="{key}", name=' in SENSOR
        assert f'kind="{kind}", metric="{key}"' in SENSOR
    assert "remember_materialized_sensors(set(DATA_MAP_KEYS), persist=True)" in SENSOR


def test_data_maps_route_sources_and_allow_only_calculated_fallback_values():
    assert 'attrs[f"{key}_source"] = entity_id' in PROFILE_DATA
    assert '("attribute", "attribute")' in PROFILE_DATA
    assert '("transform", "transform")' in PROFILE_DATA
    assert '("unit", "unit")' in PROFILE_DATA
    assert '("field", "field")' in PROFILE_DATA
    attrs_block = PROFILE_DATA.split("def routes_to_attributes", 1)[1].split("def routes_from_attributes", 1)[0]
    # Inline values are deliberately restricted to substitute facts calculated
    # by Fitness because the upstream source omitted that field. This must never
    # become a generic source-mirroring path.
    assert '_route_keeps_inline_value(route)' in attrs_block
    assert 'route.get("source_type") in INLINE_VALUE_SOURCE_TYPES' in PROFILE_DATA
    assert 'attrs[f"{key}_value"] = route["value"]' in attrs_block


def test_data_map_sensors_are_low_frequency_and_route_change_driven():
    assert "def _schedule_data_map_refresh" in SENSOR
    assert "self._data_map_refresh_handle is not None" in SENSOR
    assert "if attributes == self._data_map_attributes:" in SENSOR
    assert "self.async_write_ha_state()" in SENSOR
    # They are special-cased before the ordinary sensor listener/update path.
    added = SENSOR.split("async def async_added_to_hass", 1)[1].split("@property", 1)[0]
    assert "if self.entity_description.key in DATA_MAP_KEYS:" in added
    assert "return" in added


def test_dashboard_uses_profile_data_map_entities_as_runtime_source_of_truth():
    assert '"data_entities": data_entities' in DASHBOARD
    assert "routes_from_attributes" in DASHBOARD
    assert "_profile_data_routes" in DASHBOARD
    assert "_fitnessProfileDataRoutes = (profile, hass, kind, fallback" in FRONTEND
    assert '_fitnessProfileDataEntities(this._profile, this._hass, "live")' in FRONTEND
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.11.10"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.10"' in DASHBOARD


def test_workout_calendar_belongs_to_workouts_device():
    assert 'device_info(entry, "workout")' in CALENDAR
    assert 'device_info(entry, "evaluation")' not in CALENDAR

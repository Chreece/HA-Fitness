from pathlib import Path

R = Path('custom_components/fitness/live/runtime.py').read_text()
E = Path('custom_components/fitness/live/ha_entities.py').read_text()
C = Path('custom_components/fitness/config_flow.py').read_text()


def test_unaccepted_discoveries_do_not_create_devices():
    registration = R[R.index('def register_transport_sensor'):R.index('# Compatibility for older provider code/tests')]
    device_gate = registration[registration.index('Device Registry work is control-plane only'):registration.index('self.ensure_sensor_device(sensor.sensor_id)') + len('self.ensure_sensor_device(sensor.sensor_id)')]
    assert 'structural_change' in device_gate
    assert 'and self.sensor_is_accepted(sensor.sensor_id)' in device_gate
    assert 'if runtime.sensor_is_accepted(sensor.sensor_id)' in E
    assert 'accepted_ids' in E
    assert 'def remove_unaccepted_sensor_device' in R


def test_acceptance_is_lightweight_and_dynamic():
    section = R[R.index('def mark_sensor_accepted'):R.index('def remove_unaccepted_sensor_device')]
    assert 'self.ensure_sensor_device(sensor_id)' not in section
    assert 'self.request_hub_reload()' not in section
    assert 'self._notify_structure()' not in section


def test_discovery_card_uses_physical_sensor_name():
    assert 'self.context["title_placeholders"] = {"name": sensor.name}' in C


def test_last_seen_is_recorder_safe():
    section = E[E.index('class PhysicalLastSeenSensor'):E.index('async def async_setup_sensor_entities')]
    assert '_attr_entity_registry_enabled_default = False' in section
    assert '(seen.minute // 5) * 5' in section
    assert 'if bucket == self._last_bucket' in section


def test_passive_advertisements_do_not_save_or_notify_on_rssi_last_seen_only():
    section = R[R.index('def register_transport_sensor'):R.index('# Compatibility for older provider code/tests')]
    assert 'structural_change = (' in section
    assert 'RSSI and last_seen are intentionally volatile' in section
    assert 'if structural_change:\n            self._schedule_save()' in section
    assert 'if structural_change:\n            self._notify()' in section


def test_transport_attributes_exclude_volatile_recorder_fields():
    section = E[E.index('class PhysicalActiveTransportSensor'):E.index('class PhysicalLastSeenSensor')]
    assert '"capabilities": sorted(endpoint.capabilities)' in section
    assert 'sensor_transport_details' not in section
    active = section.split('class PhysicalSignalStrengthSensor', 1)[0]
    assert '"rssi"' not in active
    assert '"last_seen"' not in active

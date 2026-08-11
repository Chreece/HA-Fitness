import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / 'custom_components/fitness/sensor.py').read_text(encoding='utf-8')
CAP = (ROOT / 'custom_components/fitness/providers/capabilities.py').read_text(encoding='utf-8')


def _desc_keys(kind: str) -> set[str]:
    return {
        translation_key
        for _key, translation_key, found_kind in re.findall(
            r'Desc\(key="([^"]+)", translation_key="([^"]+)", kind="([^"]+)"',
            SENSOR,
        )
        if found_kind == kind
    }


def _language_files():
    base = ROOT / 'custom_components/fitness'
    yield 'en', base / 'strings.json'
    for path in sorted((base / 'translations').glob('*.json')):
        yield path.stem, path


def test_every_live_workout_sleep_sensor_localizes_its_provenance_attributes():
    expected = {
        'live': {'source_entity', 'source_device_name', 'source_integration'},
        'workout': {'sources', 'workout_start', 'field_source'},
        'sleep': {'sources', 'sleep_start', 'sleep_end', 'field_source'},
    }
    for lang, path in _language_files():
        sensors = json.loads(path.read_text(encoding='utf-8'))['entity']['sensor']
        for kind, attrs in expected.items():
            for key in _desc_keys(kind):
                assert key in sensors, (lang, kind, key)
                state_attrs = sensors[key].get('state_attributes', {})
                assert attrs <= set(state_attrs), (lang, kind, key, attrs - set(state_attrs))
                for attr in attrs:
                    assert state_attrs[attr].get('name', '').strip(), (lang, key, attr)


def test_all_setup_device_choices_centrally_exclude_fitness_output_devices():
    assert 'if "fitness" in set(_device_domains(hass, device))' in CAP
    assert 'continue' in CAP[CAP.index('def _all_devices'):CAP.index('def live_device_choices')]


def test_last_workout_ai_title_explicitly_says_evaluation_in_greek():
    data = json.loads((ROOT / 'custom_components/fitness/translations/el.json').read_text(encoding='utf-8'))
    name = data['entity']['sensor']['ai_workout_evaluation']['name']
    assert name == 'Αξιολόγηση τελευταίας προπόνησης με AI'


def test_workout_provider_domains_are_humanized_but_entity_ids_remain_exact():
    assert 'def _provider_display_name' in SENSOR
    assert 'if "." in value:' in SENSOR
    assert '"garmin_connect": "Garmin Connect"' in SENSOR
    assert 'self._provider_display_name(field_source)' in SENSOR

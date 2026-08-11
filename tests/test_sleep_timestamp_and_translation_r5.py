from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (ROOT / 'custom_components/fitness/providers/sleep_adapters/registry.py').read_text(encoding='utf-8')
SLEEP = (ROOT / 'custom_components/fitness/providers/sleep.py').read_text(encoding='utf-8')
SENSOR = (ROOT / 'custom_components/fitness/sensor.py').read_text(encoding='utf-8')


def test_sleep_alias_matching_does_not_use_raw_substring_matching():
    assert 'def _alias_matches' in REGISTRY
    assert 'normalized_alias in normalized_label' in REGISTRY
    assert 'any(_alias_matches(label, alias) for alias in aliases)' in REGISTRY


def test_numeric_sleep_timestamps_before_2000_are_rejected():
    assert '946_684_800 <= number <= 4_102_444_800' in REGISTRY
    assert '946_684_800 <= number <= 4_102_444_800' in SLEEP


def test_sleep_field_source_preserves_exact_entity_id():
    assert 'field_sources=dict(sources)' in REGISTRY
    assert '(winner.field_sources or {}).get(field_name)' in SLEEP


def test_sleep_attributes_use_friendly_provider_names():
    assert 'def _sleep_source_names' in SENSOR
    assert 'attrs["sources"] = list(dict.fromkeys(source_names))' in SENSOR


def test_sleep_common_attributes_are_localized_in_every_supported_translation():
    paths = [ROOT / 'custom_components/fitness/strings.json'] + sorted((ROOT / 'custom_components/fitness/translations').glob('*.json'))
    required = {'sources', 'sleep_start', 'sleep_end', 'field_source'}
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        sensors = data['entity']['sensor']
        for key in ('last_sleep_score', 'last_sleep_hrv', 'last_sleep_duration'):
            assert required <= set(sensors[key]['state_attributes']), (path.name, key)

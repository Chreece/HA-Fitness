from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()


def test_shared_adapters_subentry_is_legacy_only():
    assert 'LEGACY_ADAPTERS_SUBENTRY_TYPE = "adapters"' in R
    assert 'LEGACY_ADAPTERS_SUBENTRY_UNIQUE_ID = "fitness_adapters"' in R
    assert '_remove_legacy_adapters_subentry_if_empty()' in R


def test_ant_receivers_share_antplus_protocol_group_without_fake_parent():
    assert 'adapter_subentry_id("antplus")' in R
    assert 'kwargs["via_device_id"] = None' in R
    assert 'fitness_antplus_adapters' in ANT
    assert 'live_adapter:antplus' not in ANT


def test_bluetooth_adapter_has_its_own_protocol_group():
    assert 'BLUETOOTH_SUBENTRY_UNIQUE_ID = "fitness_bluetooth_adapters"' in R
    assert 'elif transport == "bluetooth":' in R
    assert 'BLUETOOTH_SUBENTRY_UNIQUE_ID = "fitness_bluetooth_adapters"' in R

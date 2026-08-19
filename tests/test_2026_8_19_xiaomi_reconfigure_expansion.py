from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_keyed_xiaomi_generations_are_registered():
    protocol = read('custom_components/fitness/device_adapters/huami_keyed/protocol.py')
    adapters = read('custom_components/fitness/device_adapters/huami_keyed/adapters.py')
    registry = read('custom_components/fitness/device_adapters/registry.py')
    for generation in range(3, 7):
        assert f'xiaomi_miband{generation}' in protocol
        assert f'MiBand{generation}Coordinator' in adapters
    assert 'HUAMI_KEYED_ARCHIVE_ADAPTERS' in registry


def test_keyed_xiaomi_auth_is_read_only_and_user_supplied():
    protocol = read('custom_components/fitness/device_adapters/huami_keyed/protocol.py')
    coordinator = read('custom_components/fitness/device_adapters/huami_keyed/coordinator.py')
    assert 'AUTH_KEY_BYTES = 16' in protocol
    assert 'fields=("auth_key",)' in coordinator
    assert 'AUTH_REQUEST_RANDOM' in coordinator
    assert 'AUTH_SEND_ENCRYPTED_PREFIX' in coordinator
    # No key-install command may be imported or written by the coordinator.
    assert 'AUTH_SEND_KEY' not in coordinator


def test_device_repair_flow_supports_secret_and_confirmation_only_paths():
    action = read('custom_components/fitness/device_user_action.py')
    repairs = read('custom_components/fitness/repairs.py')
    credentials = read('custom_components/fitness/device_credentials.py')
    assert 'is_fixable=True' in action
    assert 'TextSelectorType.PASSWORD' in repairs
    assert 'fitness_device_reconfigure_completed' in repairs
    assert 'private=True' in credentials


def test_direct_history_retries_after_reconfigure_and_forgets_credentials():
    text = read('custom_components/fitness/device_adapters/history_coordinator.py')
    assert 'fitness_device_reconfigure_completed' in text
    assert 'credential_store.async_remove' in text


def test_garmin_and_miband2_use_guided_user_action_repairs():
    garmin = read('custom_components/fitness/device_adapters/garmin/coordinator.py')
    miband2 = read('custom_components/fitness/device_adapters/miband2/coordinator.py')
    assert 'request_device_user_action(' in garmin
    assert 'request_device_user_action(' in miband2
    assert 'fitness_device_reconfigure_completed' in garmin


def test_keyed_amazfit_expansion_and_device_catalog():
    protocol = read('custom_components/fitness/device_adapters/huami_keyed/protocol.py')
    adapters = read('custom_components/fitness/device_adapters/huami_keyed/adapters.py')
    catalog = read('custom_components/fitness/live/device_catalog.json')
    for adapter_id in ('amazfit_bip_lite', 'amazfit_band5'):
        assert adapter_id in protocol
        assert adapter_id in catalog
    assert 'AmazfitBipLiteCoordinator' in adapters
    assert 'AmazfitBand5Coordinator' in adapters

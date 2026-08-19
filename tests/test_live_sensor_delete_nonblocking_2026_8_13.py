from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
SWITCH = (ROOT / "custom_components/fitness/switch.py").read_text()


def test_sensor_delete_defers_persistence_and_never_reloads_config_entries():
    start = RUNTIME.index("def _forget_sensor_memory")
    end = RUNTIME.index("def _schedule_deleted_sensor_cleanup", start)
    immediate = RUNTIME[start:end]
    assert "async_update_entry" not in immediate
    assert "async_remove_subentry" not in immediate
    assert "_schedule_profile_reloads" not in immediate

    cleanup_start = RUNTIME.index("def _schedule_deleted_sensor_cleanup")
    cleanup_end = RUNTIME.index("def forget_sensor", cleanup_start)
    cleanup = RUNTIME[cleanup_start:cleanup_end]
    assert "async_create_background_task" in cleanup
    assert "eager_start=False" in cleanup
    assert "async_update_entry" in cleanup
    assert "suppress_entry_reload_once" in cleanup
    assert "async_reload" not in cleanup
    assert "async_remove_subentry" not in cleanup
    assert "_notify_structure_throttled" not in cleanup


def test_deletion_does_not_reload_profiles_or_hub():
    start = RUNTIME.index("async def async_forget_sensor")
    end = RUNTIME.index("def _listen_for_registry_deletions", start)
    delete_path = RUNTIME[start:end]
    assert "_schedule_profile_reloads" not in delete_path
    assert "async_reload" not in delete_path
    assert "async_remove_subentry" not in delete_path


def test_adapter_switches_are_added_per_transport_subentry():
    assert 'ant_records = runtime.ant_receiver_records() if runtime.adapter_configured("antplus") else {}' in SWITCH
    assert 'for stable_key in sorted(ant_records):' in SWITCH
    assert 'bt_records = runtime.bluetooth_scanner_records() if runtime.adapter_configured("bluetooth") else {}' in SWITCH
    assert 'for source in sorted(bt_records):' in SWITCH
    assert 'config_subentry_id=runtime.adapter_subentry_id("antplus")' in SWITCH
    assert 'config_subentry_id=runtime.adapter_subentry_id("bluetooth")' in SWITCH
    broken = '''[AdapterEnabledSwitch(runtime, transport) for transport in sorted(runtime.adapter_entity_transports)],\n        config_subentry_id=runtime.adapter_subentry_id(transport)'''
    assert broken not in SWITCH

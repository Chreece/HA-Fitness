from pathlib import Path

C = Path("custom_components/fitness/config_flow.py").read_text()


def test_live_assignment_snapshots_profiles_and_updates_routing_without_reload():
    assert "profile_entries = list(runtime.profile_entries.values())" in C
    block = C[C.index("async def async_step_assign_live_sensor"):C.index("async def async_step_user")]
    assert "for entry in profile_entries:" in block
    assert "for entry in runtime.profile_entries.values():" not in block
    assert "async_update_entry(entry, options=options)" in block
    assert "runtime.suppress_entry_reload_once(entry_id)" in block
    assert "runtime.schedule_profile_assignment_refresh(changed_entries)" in block
    assert "async_reload(" not in block

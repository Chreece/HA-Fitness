from pathlib import Path

C = Path("custom_components/fitness/config_flow.py").read_text()


def test_live_assignment_snapshots_profiles_before_updates_and_reloads():
    assert "profile_entries = list(runtime.profile_entries.values())" in C
    block = C[C.index("async def async_step_assign_live_sensor"):C.index("async def async_step_user")]
    assert "for entry in profile_entries:" in block
    assert "for entry in runtime.profile_entries.values():" not in block
    # async_update_entry already invokes Fitness' update listener/reload.
    # The discovery flow must not schedule a second explicit reload.
    assert "async_update_entry(entry, options=options)" in block
    assert "async_reload(entry_id)" not in block

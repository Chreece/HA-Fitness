from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
HISTORY = (
    ROOT / "custom_components/fitness/providers/workout_history.py"
).read_text(encoding="utf-8")


def test_recorder_history_parsing_and_merging_run_in_executor():
    start = MANAGER.index("    async def async_import_workouts_from_ha_history")
    end = MANAGER.index("    @staticmethod\n    def _calendar_uid", start)
    block = MANAGER[start:end]

    assert "recorder_history_entity_metadata(self.hass, entity_ids)" in block
    assert "await self.hass.async_add_executor_job(" in block
    assert "workouts_from_recorder_history_snapshot," in block
    assert "workouts_from_recorder_history(self.hass" not in block


def test_executor_snapshot_parser_has_no_home_assistant_registry_access():
    start = HISTORY.index("def workouts_from_recorder_history_snapshot")
    end = HISTORY.index("\n\ndef workouts_from_recorder_history(", start)
    block = HISTORY[start:end]

    assert "merged_workouts(candidates)" in block
    assert "_provider_domain(" not in block
    assert "_label(" not in block
    assert "er.async_get" not in block
    assert "hass." not in block


def test_compatibility_wrapper_snapshots_metadata_before_pure_parser():
    start = HISTORY.index("def workouts_from_recorder_history(")
    end = HISTORY.index("\n\ndef _selected_provider_config_entries", start)
    block = HISTORY[start:end]

    assert "recorder_history_entity_metadata" in block
    assert "workouts_from_recorder_history_snapshot" in block

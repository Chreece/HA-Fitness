from pathlib import Path
import json
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]

if "custom_components.fitness.const" not in sys.modules:
    load_module("custom_components.fitness.const", "const.py")
workouts = load_module(
    "custom_components.fitness.providers.workouts",
    "providers/workouts.py",
)

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
DIAGNOSTICS = (
    ROOT / "custom_components/fitness/live/antplus_core/diagnostics.py"
).read_text(encoding="utf-8")


def test_workout_serialization_does_not_recursive_deepcopy_provider_payloads():
    class ExplodesOnDeepcopy:
        def __deepcopy__(self, memo):
            raise AssertionError("recursive deepcopy must not run")

    marker = ExplodesOnDeepcopy()
    workout = workouts.Workout(
        source="provider",
        start="2026-08-14T10:00:00+00:00",
        provider_values={"provider": {"nested": {"marker": marker}}},
        extra={"nested": {"marker": marker}},
    )

    stored = workout.as_dict()
    assert stored["provider_values"]["provider"]["nested"]["marker"] is marker
    assert stored["extra"]["nested"]["marker"] is marker


def test_persistent_workout_payload_is_bounded_and_route_is_downsampled():
    route = [
        {"latitude": 50.0 + index / 100_000, "longitude": 8.0}
        for index in range(20_000)
    ]
    nested = value = {}
    for _index in range(20):
        child = {}
        value["child"] = child
        value = child
    workout = workouts.Workout(
        source="provider",
        start="2026-08-14T10:00:00+00:00",
        provider_values={"provider": {"route": route, "nested": nested}},
        extra={"huge_text": "x" * 100_000},
    )

    stored = workout.as_persistent_dict()
    compact_route = stored["provider_values"]["provider"]["route"]
    assert len(compact_route) <= workouts.PERSISTENCE_MAX_LIST_ITEMS
    assert compact_route[0] == route[0]
    assert compact_route[-1] == route[-1]
    assert len(stored["extra"]["huge_text"]) == workouts.PERSISTENCE_MAX_STRING
    assert len(json.dumps(stored)) < 200_000


def test_bulk_reconciliation_merges_once_in_executor_not_once_per_candidate():
    start = MANAGER.index("    async def _async_reconcile_external_workouts")
    end = MANAGER.index("    async def async_import_provider_workout_history", start)
    block = MANAGER[start:end]
    assert "prepared.append(workout)" in block
    assert "await self._async_remember_completed_workouts(prepared)" in block
    assert "_remember_completed_workout(workout)" not in block

    start = MANAGER.index("    async def _async_remember_completed_workouts")
    end = MANAGER.index("    def _remember_completed_workouts", start)
    block = MANAGER[start:end]
    assert "await self.hass.async_add_executor_job(" in block
    assert "self._canonicalize_workout_history" in block


def test_provider_and_recorder_history_imports_use_one_batch_commit():
    provider_start = MANAGER.index("    async def async_import_provider_workout_history")
    provider_end = MANAGER.index("    async def async_import_workouts_from_ha_history", provider_start)
    provider = MANAGER[provider_start:provider_end]
    assert provider.count("await self._async_remember_completed_workouts(prepared)") == 1
    assert "_remember_completed_workout(workout)" not in provider

    recorder_start = provider_end
    recorder_end = MANAGER.index("    @staticmethod\n    def _calendar_uid", recorder_start)
    recorder = MANAGER[recorder_start:recorder_end]
    assert recorder.count("await self._async_remember_completed_workouts(prepared)") == 1
    assert "_remember_completed_workout(workout)" not in recorder


def test_ant_hot_cpu_watchdog_requires_attributable_ant_work():
    assert "ant_decode_ratio = decode_delta / wall_delta" in DIAGNOSTICS
    assert "ant_busy = ant_decode_ratio >= 0.25 or remote_delta >= 20" in DIAGNOSTICS
    assert "if remote_active and ant_busy and cpu_ratio >= 0.90:" in DIAGNOSTICS

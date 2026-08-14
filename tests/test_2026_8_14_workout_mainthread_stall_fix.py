from datetime import datetime, timedelta, timezone
from pathlib import Path
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
Workout = workouts.Workout

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def test_long_history_merge_does_not_compare_impossible_old_groups(monkeypatch):
    original = workouts._same_real_workout
    calls = 0

    def counted(a, b):
        nonlocal calls
        calls += 1
        return original(a, b)

    monkeypatch.setattr(workouts, "_same_real_workout", counted)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history = [
        Workout(
            source=f"provider_{idx}",
            sport="running",
            start=(start + timedelta(minutes=10 * idx)).isoformat(),
            duration_s=1800,
            distance_m=5000,
        )
        for idx in range(1000)
    ]

    merged = workouts.merged_workouts(history)
    assert len(merged) == 1000
    # Ten-minute-separated workouts are outside the hard five-minute identity
    # window, so the optimized clusterer must retire old groups before matching.
    assert calls == 0


def test_newest_only_merges_final_five_minute_window(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history = [
        Workout(
            source=f"provider_{idx}",
            sport="running",
            start=(start + timedelta(hours=idx)).isoformat(),
            duration_s=1800,
        )
        for idx in range(1000)
    ]
    history.append(
        Workout(
            source="second_view_of_latest",
            sport="running",
            start=(start + timedelta(hours=999, minutes=3)).isoformat(),
            duration_s=1800,
        )
    )

    seen_sizes = []
    original = workouts.merged_workouts

    def recording(items):
        seen_sizes.append(len(items))
        return original(items)

    monkeypatch.setattr(workouts, "merged_workouts", recording)
    result = workouts.newest(history)

    assert result is not None
    assert seen_sizes == [2]


def test_general_notify_does_not_invalidate_historical_evaluation_cache():
    start = MANAGER.index("    def _notify(self):")
    end = MANAGER.index("    def _notify_live(self):", start)
    block = MANAGER[start:end]
    assert "_invalidate_evaluation_cache" not in block

    profile_start = MANAGER.index("    def _async_profile_source_change")
    profile_end = MANAGER.index("    @staticmethod", profile_start)
    assert "_invalidate_evaluation_cache()" in MANAGER[profile_start:profile_end]

    workout_start = MANAGER.index("    def _notify_workout_history")
    workout_end = MANAGER.index("    def _sleep_records_from_history", workout_start)
    assert "_invalidate_workout_history_cache()" in MANAGER[workout_start:workout_end]


def test_local_workouts_caches_canonical_history_until_real_mutation():
    start = MANAGER.index("    def local_workouts(self)")
    end = MANAGER.index("    def latest_workout(self)", start)
    block = MANAGER[start:end]
    assert 'getattr(self, "_local_workouts_cache", None)' in block
    assert "merged = merged_workouts(result)" in block
    assert "self._local_workouts_cache = tuple(merged)" in block

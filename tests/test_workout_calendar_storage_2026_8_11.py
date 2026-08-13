"""Storage, retention and deletion checks for the 2026.8.11 workout calendar.

The normal project test environment intentionally does not install Home
Assistant Core. To keep these tests fast and consistent with the rest of the
suite, the exact relevant FitnessManager method bodies are loaded from
manager.py with AST and executed on a lightweight harness.
"""
from __future__ import annotations

import ast
import asyncio
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]

const = load_module("custom_components.fitness.const", "const.py")
workouts = load_module("custom_components.fitness.providers.workouts", "providers/workouts.py")
Workout = workouts.Workout

_METHODS = {
    "workout_retention_days",
    "_retention_cutoff",
    "_bulk_deleted_cutoff",
    "_workout_is_outside_retention",
    "_prune_workout_history",
    "async_delete_workouts_before",
    "_calendar_uid",
    "_workout_is_deleted",
    "async_delete_calendar_workout",
    "_remember_completed_workout",
    "local_workouts",
}


def _load_manager_methods():
    source = (FITNESS / "manager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    manager_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FitnessManager"
    )
    selected = [
        node for node in manager_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in _METHODS
    ]
    assert {node.name for node in selected} == _METHODS

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "datetime": datetime,
        "timezone": timezone,
        "timedelta": timedelta,
        "json": json,
        "Workout": Workout,
        "_dt": workouts._dt,
        "_same_real_workout": workouts._same_real_workout,
        "merged_workouts": workouts.merged_workouts,
        "CONF_WORKOUT_RETENTION_DAYS": const.CONF_WORKOUT_RETENTION_DAYS,
        "DEFAULT_WORKOUT_RETENTION_DAYS": const.DEFAULT_WORKOUT_RETENTION_DAYS,
        "MAX_WORKOUT_RETENTION_DAYS": const.MAX_WORKOUT_RETENTION_DAYS,
    }
    exec(compile(module, str(FITNESS / "manager.py"), "exec"), namespace)
    return namespace


_MANAGER_METHODS = _load_manager_methods()


class ManagerHarness:
    pass


for _name in _METHODS:
    setattr(ManagerHarness, _name, _MANAGER_METHODS[_name])


def _manager(*, retention_days: int = const.DEFAULT_WORKOUT_RETENTION_DAYS) -> ManagerHarness:
    manager = ManagerHarness()
    manager.config = {const.CONF_WORKOUT_RETENTION_DAYS: retention_days}
    manager.history = []
    manager.deleted_workouts = []
    manager.deleted_workouts_before = None
    manager._save = AsyncMock()
    manager._notify = MagicMock()
    manager._notify_workout_history = MagicMock()
    return manager



def _run_async(coro):
    """Run a coroutine and leave a valid current loop for older tests.

    Python 3.13 warns when code asks for an implicitly-created current loop,
    so this helper creates and installs its loops explicitly.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        # Several older HA-Fitness tests still expect a current loop after
        # this test file has run.
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_deleted_workout_is_tombstoned_and_not_reimported():
    async def run():
        manager = _manager(retention_days=0)
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        manager.history = [
            Workout(
                source="sensor.garmin",
                name="Morning Run",
                sport="running",
                start=start.isoformat(),
                duration_s=1800,
                distance_m=5000,
            ).as_dict()
        ]

        uid = manager._calendar_uid("entry", manager.local_workouts()[0])
        assert uid is not None
        assert await manager.async_delete_calendar_workout(uid, "entry") is True
        assert manager.history == []
        assert len(manager.deleted_workouts) == 1

        same_from_strava = Workout(
            source="sensor.strava",
            name="Morning Run",
            sport="running",
            start=(start + timedelta(seconds=20)).isoformat(),
            duration_s=1802,
            distance_m=5005,
        )
        assert manager._workout_is_deleted(same_from_strava) is True
        assert manager._remember_completed_workout(same_from_strava) is False
        assert manager.history == []

    _run_async(run())


def test_delete_does_not_tombstone_unrelated_workout():
    async def run():
        manager = _manager(retention_days=0)
        now = datetime.now(timezone.utc)
        first = Workout(
            source="sensor.garmin",
            sport="running",
            start=(now - timedelta(hours=3)).isoformat(),
            duration_s=1800,
            distance_m=5000,
        )
        second = Workout(
            source="sensor.garmin",
            sport="running",
            start=(now - timedelta(hours=1)).isoformat(),
            duration_s=1800,
            distance_m=5000,
        )
        manager.history = [first.as_dict(), second.as_dict()]

        uid = manager._calendar_uid("entry", first)
        assert await manager.async_delete_calendar_workout(uid, "entry") is True
        remaining = manager.local_workouts()
        assert len(remaining) == 1
        assert remaining[0].start == second.start
        assert manager._workout_is_deleted(second) is False

    _run_async(run())


def test_retention_zero_is_unlimited():
    manager = _manager(retention_days=0)
    very_old = Workout(
        source="sensor.garmin",
        sport="running",
        start=(datetime.now(timezone.utc) - timedelta(days=20000)).isoformat(),
        duration_s=1800,
    )
    manager.history = [very_old.as_dict()]

    assert manager.workout_retention_days() == 0
    assert manager._prune_workout_history() is False
    assert len(manager.history) == 1


def test_configured_retention_prunes_only_older_workouts():
    manager = _manager(retention_days=30)
    now = datetime.now(timezone.utc)
    old = Workout(
        source="sensor.garmin",
        sport="running",
        start=(now - timedelta(days=31)).isoformat(),
        duration_s=1800,
    )
    recent = Workout(
        source="sensor.garmin",
        sport="running",
        start=(now - timedelta(days=29)).isoformat(),
        duration_s=1800,
    )
    manager.history = [old.as_dict(), recent.as_dict()]

    assert manager._prune_workout_history() is True
    assert [item["start"] for item in manager.history] == [recent.start]


def test_bulk_delete_uses_one_persistent_cutoff_and_blocks_reimport():
    async def run():
        manager = _manager(retention_days=0)
        now = datetime.now(timezone.utc)
        old = Workout(
            source="sensor.garmin",
            sport="running",
            start=(now - timedelta(days=100)).isoformat(),
            duration_s=1800,
        )
        recent = Workout(
            source="sensor.garmin",
            sport="running",
            start=(now - timedelta(days=10)).isoformat(),
            duration_s=1800,
        )
        manager.history = [old.as_dict(), recent.as_dict()]

        deleted = await manager.async_delete_workouts_before(30)

        assert deleted == 1
        assert len(manager.history) == 1
        assert manager.history[0]["start"] == recent.start
        assert manager.deleted_workouts_before is not None
        assert manager.deleted_workouts == []
        assert manager._workout_is_deleted(old) is True
        assert manager._remember_completed_workout(old) is False

    _run_async(run())


def test_async_test_runner_leaves_valid_current_event_loop():
    async def run():
        return asyncio.get_running_loop() is not None

    assert _run_async(run()) is True

    # The helper deliberately installs a fresh loop after closing its private
    # test loop. The important contract for the rest of this legacy test suite
    # is that get_event_loop() still returns a usable, open current loop.
    current = asyncio.get_event_loop()
    assert current is not None
    assert not current.is_closed()
    assert not current.is_running()

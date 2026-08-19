"""Canonical planned workouts and built-in fitness tests for Fitness."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

MAX_STEPS = 64
MAX_TEXT = 500


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def normalize_prescription(raw: dict[str, Any], *, source: str = "fitness") -> dict[str, Any]:
    """Normalize an AI/manual/test workout into one bounded executable model."""
    if not isinstance(raw, dict):
        raise ValueError("prescription must be an object")
    steps = []
    for index, item in enumerate(raw.get("steps") or []):
        if not isinstance(item, dict):
            continue
        duration = item.get("duration_seconds")
        try:
            duration = max(0, min(86400, int(duration))) if duration is not None else None
        except (TypeError, ValueError):
            duration = None
        reps = item.get("repetitions")
        try:
            reps = max(1, min(100, int(reps))) if reps is not None else None
        except (TypeError, ValueError):
            reps = None
        steps.append({
            "index": index,
            "name": _text(item.get("name") or item.get("instruction") or f"Step {index + 1}", 120),
            "instruction": _text(item.get("instruction") or item.get("name"), 500),
            "duration_seconds": duration,
            "distance_m": item.get("distance_m"),
            "repetitions": reps,
            "target": deepcopy(item.get("target")) if isinstance(item.get("target"), dict) else {},
            "recovery_seconds": item.get("recovery_seconds"),
        })
        if len(steps) >= MAX_STEPS:
            break
    return {
        "schema_version": 1,
        "id": _text(raw.get("id"), 128),
        "source": _text(raw.get("source") or source, 64),
        "name": _text(raw.get("name") or raw.get("recommendation") or "Workout", 160),
        "sport": _text(raw.get("sport") or "other", 64).lower(),
        "goal": _text(raw.get("goal"), 300),
        "notes": _text(raw.get("notes"), 1000),
        "duration_minutes": raw.get("duration_minutes"),
        "steps": steps,
    }


FITNESS_TESTS = {
    "running_cooper_12min": {
        "id": "running_cooper_12min", "name": "Cooper 12-minute run", "sport": "running",
        "goal": "Estimate aerobic running fitness from maximum sustainable distance in 12 minutes.",
        "steps": [
            {"name": "Warm up", "instruction": "Run easily and prepare for a hard continuous effort.", "duration_seconds": 600, "target": {"effort": "easy"}},
            {"name": "12-minute test", "instruction": "Cover as much distance as you safely can at an even hard effort.", "duration_seconds": 720, "target": {"effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Walk or jog easily.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "cycling_ftp_20min": {
        "id": "cycling_ftp_20min", "name": "Cycling 20-minute FTP test", "sport": "cycling",
        "goal": "Record a controlled maximal 20-minute power effort for FTP estimation.",
        "steps": [
            {"name": "Warm up", "instruction": "Ride progressively from easy to moderate.", "duration_seconds": 900, "target": {"effort": "easy_to_moderate"}},
            {"name": "Openers", "instruction": "Ride three short hard efforts with easy recovery.", "duration_seconds": 360, "repetitions": 3, "target": {"effort": "hard"}},
            {"name": "Recovery", "instruction": "Ride easily before the test.", "duration_seconds": 300, "target": {"effort": "easy"}},
            {"name": "20-minute test", "instruction": "Hold the highest even power you can sustain for the full 20 minutes.", "duration_seconds": 1200, "target": {"metric": "power", "effort": "max_sustainable"}},
            {"name": "Cool down", "instruction": "Ride easily.", "duration_seconds": 600, "target": {"effort": "easy"}},
        ],
    },
    "strength_submax_1rm": {
        "id": "strength_submax_1rm", "name": "Submaximal strength test", "sport": "strength",
        "goal": "Estimate strength from a controlled submaximal set without requiring a true one-repetition maximum.",
        "steps": [
            {"name": "Specific warm up", "instruction": "Warm up the selected exercise with progressively heavier comfortable sets.", "duration_seconds": 600},
            {"name": "Test set", "instruction": "Perform one technically clean set with a known load, stopping before form breaks. Record load and repetitions.", "target": {"effort": "hard_submaximal"}},
            {"name": "Recovery", "instruction": "Finish the test and recover. Do not repeat a maximal set solely to improve the score.", "duration_seconds": 300},
        ],
    },
}


def fitness_test_catalog() -> list[dict[str, Any]]:
    return [normalize_prescription({**value, "source": "fitness_test"}) for value in FITNESS_TESTS.values()]


def fitness_test(test_id: str) -> dict[str, Any]:
    raw = FITNESS_TESTS.get(str(test_id))
    if raw is None:
        raise KeyError(test_id)
    return normalize_prescription({**raw, "source": "fitness_test"})

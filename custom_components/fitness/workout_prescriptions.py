"""Canonical planned workouts and built-in fitness tests for Fitness."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

MAX_STEPS = 64
MAX_TEXT = 500

_AEROBIC_SPORTS = {
    "cycling", "indoor_cycling", "running", "treadmill", "walking", "hiking",
    "rowing", "swimming", "elliptical", "cardio", "cross_country_skiing",
}
_ZONE_FOR_INTENSITY = {
    "recovery": "zone_1",
    "very_light": "zone_1",
    "light": "zone_2",
    "moderate": "zone_3",
    "vigorous": "zone_4",
    "near_maximal": "zone_5",
}


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def _canonical_intensity(value: Any) -> str:
    """Return one stable intensity token from AI/manual target wording."""
    text = _text(value, 80).lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text in {"recovery", "very_light", "light", "moderate", "vigorous", "near_maximal"}:
        return text
    if any(token in text for token in ("recovery", "recover", "cool_down", "cooldown", "very_easy")):
        return "recovery"
    if any(token in text for token in ("near_max", "maximal", "max_sustainable", "sprint", "all_out")):
        return "near_maximal"
    if any(token in text for token in ("vigorous", "threshold", "hard", "vo2", "interval")):
        return "vigorous"
    if any(token in text for token in ("moderate", "tempo", "steady", "aerobic")):
        return "moderate"
    if any(token in text for token in ("light", "easy", "warm_up", "warmup")):
        return "light"
    return text[:80]


def _canonical_zone(value: Any) -> str:
    """Normalize Zone 1..5 representations without inventing a zone."""
    text = _text(value, 40).lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    if text in {f"zone_{index}" for index in range(1, 6)}:
        return text
    if text.isdigit() and 1 <= int(text) <= 5:
        return f"zone_{int(text)}"
    for index in range(1, 6):
        if f"zone{index}" in text or f"zone_{index}" in text:
            return f"zone_{index}"
    return ""


def _normalize_training_target(
    target: dict[str, Any],
    *,
    sport: str,
    step_name: str,
    instruction: str,
    workout_intensity: str,
) -> dict[str, Any]:
    """Preserve target details while adding canonical intensity/zone metadata."""
    result = deepcopy(target)
    explicit_zone = _canonical_zone(result.get("training_zone") or result.get("zone"))
    intensity = _canonical_intensity(result.get("intensity") or result.get("effort"))
    hint = f"{step_name} {instruction}".lower()
    if not intensity:
        hinted = _canonical_intensity(hint)
        intensity = hinted if hinted in _ZONE_FOR_INTENSITY else ""
    # Warm-up/cool-down wording is more specific than an overall workout level.
    if not intensity:
        intensity = workout_intensity
    if intensity:
        result["intensity"] = intensity
    if explicit_zone:
        result["training_zone"] = explicit_zone
    elif sport in _AEROBIC_SPORTS and intensity in _ZONE_FOR_INTENSITY:
        result["training_zone"] = _ZONE_FOR_INTENSITY[intensity]
    result.pop("zone", None)
    return result


def normalize_prescription(raw: dict[str, Any], *, source: str = "fitness") -> dict[str, Any]:
    """Normalize an AI/manual/test workout into one bounded executable model."""
    if not isinstance(raw, dict):
        raise ValueError("prescription must be an object")
    sport = _text(raw.get("sport") or "other", 64).lower()
    workout_intensity = _canonical_intensity(raw.get("intensity"))
    workout_zone = _canonical_zone(raw.get("training_zone") or raw.get("zone"))
    if not workout_zone and sport in _AEROBIC_SPORTS and workout_intensity in _ZONE_FOR_INTENSITY:
        workout_zone = _ZONE_FOR_INTENSITY[workout_intensity]
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
        step_name = _text(item.get("name") or item.get("instruction") or f"Step {index + 1}", 120)
        instruction = _text(item.get("instruction") or item.get("name"), 500)
        target = _normalize_training_target(
            item.get("target") if isinstance(item.get("target"), dict) else {},
            sport=sport,
            step_name=step_name,
            instruction=instruction,
            workout_intensity=workout_intensity,
        )
        steps.append({
            "index": index,
            "name": step_name,
            "instruction": instruction,
            "duration_seconds": duration,
            "distance_m": item.get("distance_m"),
            "repetitions": reps,
            "target": target,
            "recovery_seconds": item.get("recovery_seconds"),
        })
        if len(steps) >= MAX_STEPS:
            break
    return {
        "schema_version": 1,
        "id": _text(raw.get("id"), 128),
        "source": _text(raw.get("source") or source, 64),
        "name": _text(raw.get("name") or raw.get("recommendation") or "Workout", 160),
        "sport": sport,
        "intensity": workout_intensity,
        "training_zone": workout_zone,
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

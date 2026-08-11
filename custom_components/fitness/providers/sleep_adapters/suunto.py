"""Sleep adapter contract for Suunto."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("suunto", ("suunto",), {
        "duration_s": ("sleep_duration", "total_sleep"),
        "deep_sleep_s": ("deep_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "awake_s": ("awake_time",),
        "score": ("sleep_score",),
        "hrv_ms": ("hrv",),
        "average_hr": ("sleep_heart_rate", "resting_heart_rate"),
        "recovery_score": ("recovery_score",),
    })

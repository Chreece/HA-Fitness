"""Sleep adapter contract for Eight Sleep."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("eight_sleep", ("eight_sleep", "eightsleep"), {
        "duration_s": ("sleep_duration",),
        "score": ("sleep_score",),
        "time_in_bed_s": ("time_in_bed",),
        "deep_sleep_s": ("deep_sleep",),
        "light_sleep_s": ("light_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "awake_s": ("awake",),
        "average_hr": ("heart_rate",),
        "hrv_ms": ("hrv",),
        "respiratory_rate": ("respiratory_rate",),
        "in_bed": ("bed_presence", "in_bed"),
    })

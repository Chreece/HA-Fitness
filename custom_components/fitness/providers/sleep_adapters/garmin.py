"""Sleep adapter contract for Garmin."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("garmin", ("garmin_connect",), {
        "duration_s": ("total_sleep_duration", "sleep_duration"),
        "awake_s": ("awake_duration",),
        "light_sleep_s": ("light_sleep",),
        "deep_sleep_s": ("deep_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "score": ("sleep_score",),
        "hrv_ms": ("hrv_last_night_average", "hrv_last_night"),
        "sleep_need_s": ("sleep_need",),
        "start": ("bedtime",),
        "end": ("wake_time",),
    })

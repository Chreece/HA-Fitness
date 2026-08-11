"""Sleep adapter contract for Oura."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("oura", ("oura",), {
        "duration_s": ("total_sleep_duration",),
        "time_in_bed_s": ("time_in_bed",),
        "awake_s": ("awake_time",),
        "light_sleep_s": ("light_sleep_duration",),
        "deep_sleep_s": ("deep_sleep_duration",),
        "rem_sleep_s": ("rem_sleep_duration",),
        "sleep_latency_s": ("sleep_latency",),
        "score": ("sleep_score",),
        "efficiency_percent": ("sleep_efficiency",),
        "average_hr": ("average_sleep_heart_rate",),
        "minimum_hr": ("lowest_sleep_heart_rate",),
        "hrv_ms": ("average_sleep_hrv",),
        "readiness_score": ("readiness_score",),
        "start": ("bedtime_start",),
        "end": ("bedtime_end",),
    })

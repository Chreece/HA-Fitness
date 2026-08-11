"""Sleep adapter contract for Sleepiq."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("sleepiq", ("sleepiq",), {
        "duration_s": ("sleep_duration",),
        "score": ("sleep_score", "sleep_number"),
        "average_hr": ("heart_rate_avg", "heart_rate_average"),
        "hrv_ms": ("hrv",),
        "respiratory_rate": ("respiratory_rate_avg", "respiratory_rate_average"),
        "in_bed": ("is_in_bed", "in_bed"),
    })

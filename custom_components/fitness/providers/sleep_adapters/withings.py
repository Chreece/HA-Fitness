"""Sleep adapter contract for Withings."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("withings", ("withings",), {
        "deep_sleep_s": ("sleep_deep_duration",),
        "light_sleep_s": ("sleep_light_duration",),
        "rem_sleep_s": ("sleep_rem_duration",),
        "awake_s": ("sleep_wakeup_duration",),
        "sleep_latency_s": ("sleep_tosleep_duration",),
        "score": ("sleep_score",),
        "average_hr": ("sleep_heart_rate_average",),
        "respiratory_rate": ("sleep_respiratory_average",),
        "disturbance_count": ("sleep_wakeup_count",),
        "in_bed": ("in_bed",),
    })

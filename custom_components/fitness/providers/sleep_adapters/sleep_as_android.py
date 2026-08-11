"""Sleep adapter contract for Sleep As Android."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("sleep_as_android", ("sleep_as_android",), {
        # HACS variants may expose aggregate sensors. Core HA mainly exposes
        # event entities; those are handled below as a basic start/stop record.
        "duration_s": ("sleep_duration",),
        "deep_sleep_s": ("deep_sleep_duration", "deep_sleep_percent"),
        "score": ("sleep_score", "sleep_quality"),
        "average_hr": ("sleep_heart_rate",),
    })

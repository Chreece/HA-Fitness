"""Sleep adapter contract for Fitbit."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("fitbit", ("fitbit",), {
        "duration_s": ("minutes_asleep", "minutesasleep", "sleep_duration"),
        "time_in_bed_s": ("time_in_bed", "timeinbed"),
        "awake_s": ("minutes_awake", "minutesawake"),
        "sleep_latency_s": ("minutes_to_fall_asleep", "minutestofallasleep"),
        "efficiency_percent": ("sleep_efficiency", "efficiency"),
        "disturbance_count": ("awakenings_count", "awakeningscount"),
    })

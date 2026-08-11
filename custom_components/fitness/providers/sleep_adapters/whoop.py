"""Sleep adapter contract for Whoop."""
from __future__ import annotations

from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("whoop", ("whoop",), {
        "score": ("sleep_performance",),
        "efficiency_percent": ("sleep_efficiency",),
        "time_in_bed_s": ("time_in_bed", "total_in_bed_time"),
        "awake_s": ("awake_time", "total_awake_time"),
        "light_sleep_s": ("light_sleep", "total_light_sleep_time"),
        "deep_sleep_s": ("sws_time", "slow_wave_sleep", "total_slow_wave_sleep_time"),
        "rem_sleep_s": ("rem_sleep", "total_rem_sleep_time"),
        "respiratory_rate": ("respiratory_rate",),
        "sleep_cycle_count": ("sleep_cycle",),
        "disturbance_count": ("disturbance",),
        "sleep_need_s": ("sleep_need", "baseline_need"),
        "sleep_debt_s": ("sleep_debt",),
        "recovery_score": ("recovery_score",),
        "hrv_ms": ("hrv",),
        "average_hr": ("resting_heart_rate",),
        "spo2_percent": ("spo2",),
    })

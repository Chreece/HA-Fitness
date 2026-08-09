"""Scientifically transparent real-time derived fitness metrics."""

from __future__ import annotations


def percent_max_hr(current_hr: float | None, max_hr: float | None) -> float | None:
    if current_hr is None or max_hr is None or max_hr <= 0:
        return None
    return current_hr / max_hr * 100.0


def percent_hrr(
    current_hr: float | None,
    max_hr: float | None,
    resting_hr: float | None,
) -> float | None:
    if current_hr is None or max_hr is None or resting_hr is None:
        return None
    reserve = max_hr - resting_hr
    if reserve <= 0:
        return None
    return (current_hr - resting_hr) / reserve * 100.0


def acsm_hrr_intensity(hrr_percent: float | None) -> str | None:
    """ACSM relative aerobic intensity classification using %HRR.

    <30 very light
    30-39 light
    40-59 moderate
    60-89 vigorous
    >=90 near-maximal/maximal
    """
    if hrr_percent is None:
        return None
    if hrr_percent < 30:
        return "very_light"
    if hrr_percent < 40:
        return "light"
    if hrr_percent < 60:
        return "moderate"
    if hrr_percent < 90:
        return "vigorous"
    return "near_maximal"


def relative_percent(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None or reference <= 0:
        return None
    return current / reference * 100.0


def pace_from_speed_kmh(speed_kmh: float | None) -> float | None:
    if speed_kmh is None or speed_kmh <= 0:
        return None
    return 60.0 / speed_kmh


def speed_from_pace_min_km(pace: float | None) -> float | None:
    if pace is None or pace <= 0:
        return None
    return 60.0 / pace

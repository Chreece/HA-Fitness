"""Heart-rate calculations."""


def predicted_max_hr_tanaka(age: int) -> float:
    """Tanaka et al. 2001: 208 - 0.7*age."""
    return 208.0 - 0.7 * age


def heart_rate_reserve(max_hr: float, resting_hr: float) -> float:
    return max_hr - resting_hr


def hrr_percent(current_hr: float, max_hr: float, resting_hr: float) -> float | None:
    reserve = max_hr - resting_hr
    if reserve <= 0:
        return None
    return (current_hr - resting_hr) / reserve * 100.0

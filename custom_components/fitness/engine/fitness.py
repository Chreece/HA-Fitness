"""Scientific/transparent fitness calculations."""


def uth_vo2max(max_hr: float, resting_hr: float) -> float | None:
    """Uth et al. 2004 HR-ratio estimate.

    Original validation population was well-trained men; provenance must remain
    visible when used outside that population.
    """
    if max_hr <= 0 or resting_hr <= 0:
        return None
    return 15.3 * max_hr / resting_hr


def friend_predicted_vo2max(age: int, sex: str | None, weight_kg: float | None) -> float | None:
    """FRIEND 2017 reference equation.

    VO2max = 79.9 - 0.39*age - 13.7*gender - 0.127*weight(lb)
    gender: male=0, female=1.
    """
    if weight_kg is None or weight_kg <= 0 or sex not in ("male", "female"):
        return None
    gender = 0 if sex == "male" else 1
    weight_lb = weight_kg * 2.2046226218
    return 79.9 - 0.39 * age - 13.7 * gender - 0.127 * weight_lb


def percent_predicted(measured: float | None, predicted: float | None) -> float | None:
    if measured is None or predicted is None or predicted <= 0:
        return None
    return measured / predicted * 100.0


def reference_status(percent: float | None) -> str | None:
    """Human-readable reference comparison.

    The scientific output is percent-predicted. These bands are display
    conventions, deliberately exposed as such rather than medical cutoffs.
    """
    if percent is None:
        return None
    if percent < 90:
        return "below_reference"
    if percent <= 110:
        return "around_reference"
    return "above_reference"


def hrv_personal_status(
    nightly: float | None,
    baseline_low: float | None,
    baseline_high: float | None,
) -> str | None:
    """Compare nightly HRV against the person's established baseline band."""
    if nightly is None or baseline_low is None or baseline_high is None:
        return None
    if nightly < baseline_low:
        return "below_personal_baseline"
    if nightly > baseline_high:
        return "above_personal_baseline"
    return "within_personal_baseline"


def threshold_pace_from_speed(speed_m_s: float | None) -> float | None:
    """Convert physiologically plausible running threshold speed to min/km."""
    if speed_m_s is None or speed_m_s < 1.5 or speed_m_s > 8.0:
        return None
    return 1000.0 / speed_m_s / 60.0

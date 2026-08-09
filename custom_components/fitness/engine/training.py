"""Scientifically grounded workout/session calculations.

These metrics are descriptive training metrics, not medical diagnoses.
"""

from __future__ import annotations

from math import exp
from statistics import mean, pstdev
from typing import Any


def fractional_hr_reserve(
    heart_rate: float | None,
    resting_hr: float | None,
    max_hr: float | None,
) -> float | None:
    if heart_rate is None or resting_hr is None or max_hr is None:
        return None
    reserve = max_hr - resting_hr
    if reserve <= 0:
        return None
    return max(0.0, min(1.5, (heart_rate - resting_hr) / reserve))


def banister_trimp(
    duration_minutes: float | None,
    average_hr: float | None,
    resting_hr: float | None,
    max_hr: float | None,
    sex: str | None,
) -> float | None:
    """Classic Banister TRIMP using mean HR and session duration."""
    if duration_minutes is None or duration_minutes <= 0:
        return None
    hrr = fractional_hr_reserve(
        average_hr,
        resting_hr,
        max_hr,
    )
    if hrr is None:
        return None

    sex_value = str(sex or "").strip().lower()
    if sex_value in ("female", "f", "woman"):
        weighting = 0.86 * exp(1.67 * hrr)
    else:
        # Original male coefficients are also used as the deterministic
        # fallback when sex is unavailable.
        weighting = 0.64 * exp(1.92 * hrr)

    return duration_minutes * hrr * weighting


def mechanical_work_kj(samples: list[dict[str, Any]]) -> float | None:
    """Integrate power over time to mechanical work in kJ."""
    points = []
    for sample in samples:
        power = sample.get("power")
        timestamp = sample.get("_timestamp_epoch")
        if power is None or timestamp is None:
            continue
        try:
            points.append((float(timestamp), float(power)))
        except (TypeError, ValueError):
            continue

    if len(points) < 2:
        return None

    points.sort()
    joules = 0.0
    for (ta, pa), (tb, pb) in zip(points, points[1:]):
        dt = tb - ta
        # Ignore huge gaps rather than integrating stale values.
        if dt <= 0 or dt > 30:
            continue
        joules += ((pa + pb) / 2.0) * dt

    return joules / 1000.0 if joules > 0 else None


def time_in_hrr_intensity(
    samples: list[dict[str, Any]],
    resting_hr: float | None,
    max_hr: float | None,
) -> dict[str, float]:
    """Seconds spent in population HRR intensity classifications."""
    result = {
        "very_light": 0.0,
        "light": 0.0,
        "moderate": 0.0,
        "vigorous": 0.0,
        "near_maximal": 0.0,
    }

    if resting_hr is None or max_hr is None:
        return result

    usable = []
    for sample in samples:
        hr = sample.get("heart_rate")
        ts = sample.get("_timestamp_epoch")
        if hr is None or ts is None:
            continue
        try:
            usable.append((float(ts), float(hr)))
        except (TypeError, ValueError):
            continue

    usable.sort()
    for (ta, hr), (tb, _) in zip(usable, usable[1:]):
        dt = tb - ta
        if dt <= 0 or dt > 30:
            continue

        fraction = fractional_hr_reserve(hr, resting_hr, max_hr)
        if fraction is None:
            continue

        pct = fraction * 100
        if pct < 30:
            key = "very_light"
        elif pct < 40:
            key = "light"
        elif pct < 60:
            key = "moderate"
        elif pct < 90:
            key = "vigorous"
        else:
            key = "near_maximal"
        result[key] += dt

    return {key: round(value, 1) for key, value in result.items()}


def aerobic_efficiency_and_decoupling(
    samples: list[dict[str, Any]],
    duration_seconds: float,
) -> dict[str, Any]:
    """Describe HR/external-work coupling across the session.

    Prefer power/HR when power exists; otherwise use speed/HR.
    Decoupling is only returned for sessions >=20 minutes with enough samples.
    """
    if duration_seconds <= 0:
        return {
            "efficiency": None,
            "efficiency_kind": None,
            "decoupling_percent": None,
        }

    rows = []
    for sample in samples:
        ts = sample.get("_timestamp_epoch")
        hr = sample.get("heart_rate")
        if ts is None or hr is None:
            continue
        try:
            ts = float(ts)
            hr = float(hr)
        except (TypeError, ValueError):
            continue
        if hr <= 0:
            continue

        power = sample.get("power")
        speed = sample.get("speed")

        if power is not None:
            try:
                external = float(power)
                if external > 0:
                    rows.append((ts, external / hr, "power_hr"))
                    continue
            except (TypeError, ValueError):
                pass

        if speed is not None:
            try:
                external = float(speed)
                if external > 0:
                    rows.append((ts, external / hr, "speed_hr"))
            except (TypeError, ValueError):
                pass

    if len(rows) < 6:
        return {
            "efficiency": None,
            "efficiency_kind": None,
            "decoupling_percent": None,
        }

    # Use whichever relation dominates the session.
    kinds = [row[2] for row in rows]
    kind = (
        "power_hr"
        if kinds.count("power_hr") >= kinds.count("speed_hr")
        else "speed_hr"
    )
    rows = [row for row in rows if row[2] == kind]
    if len(rows) < 6:
        return {
            "efficiency": None,
            "efficiency_kind": None,
            "decoupling_percent": None,
        }

    values = [row[1] for row in rows]
    efficiency = mean(values)

    decoupling = None
    if duration_seconds >= 20 * 60 and len(rows) >= 12:
        midpoint = rows[0][0] + (rows[-1][0] - rows[0][0]) / 2
        first = [value for ts, value, _ in rows if ts <= midpoint]
        second = [value for ts, value, _ in rows if ts > midpoint]
        if len(first) >= 4 and len(second) >= 4:
            first_mean = mean(first)
            second_mean = mean(second)
            if first_mean > 0:
                decoupling = ((first_mean - second_mean) / first_mean) * 100

    return {
        "efficiency": round(efficiency, 5),
        "efficiency_kind": kind,
        "decoupling_percent": (
            round(decoupling, 2)
            if decoupling is not None
            else None
        ),
    }


def coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    if avg == 0:
        return None
    return pstdev(values) / abs(avg) * 100

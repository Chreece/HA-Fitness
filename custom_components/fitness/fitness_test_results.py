"""Deterministic result extraction for built-in Fitness performance tests."""
from __future__ import annotations

from statistics import mean
from typing import Any

from .const import METRIC_DISTANCE, METRIC_HEART_RATE, METRIC_POWER


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _step_samples(samples: list[dict[str, Any]], step: int) -> list[dict[str, Any]]:
    rows = [
        row for row in samples
        if isinstance(row, dict) and row.get("_prescription_step") == step
    ]
    return sorted(rows, key=lambda row: _number(row.get("_timestamp_epoch")) or 0.0)


def _elapsed_seconds(rows: list[dict[str, Any]]) -> float | None:
    stamps = [
        stamp for row in rows
        if (stamp := _number(row.get("_timestamp_epoch"))) is not None
    ]
    if len(stamps) < 2:
        return None
    return max(0.0, max(stamps) - min(stamps))


def _distance_m(rows: list[dict[str, Any]]) -> float | None:
    # Fitness' canonical live distance is kilometres.
    values = [
        value for row in rows
        if (value := _number(row.get(METRIC_DISTANCE))) is not None
    ]
    if not values:
        return None
    delta_km = max(values) - min(values)
    if delta_km <= 0 and len(values) == 1:
        return None
    return max(0.0, delta_km * 1000.0)


def _mean_metric(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = [
        value for row in rows
        if (value := _number(row.get(metric))) is not None
    ]
    return mean(values) if values else None


def _last_metric(rows: list[dict[str, Any]], metric: str) -> float | None:
    for row in reversed(rows):
        value = _number(row.get(metric))
        if value is not None:
            return value
    return None


def _last_seconds_mean(rows: list[dict[str, Any]], metric: str, seconds: float) -> float | None:
    if not rows:
        return None
    end = max(
        (_number(row.get("_timestamp_epoch")) or 0.0 for row in rows),
        default=0.0,
    )
    values = []
    for row in rows:
        stamp = _number(row.get("_timestamp_epoch"))
        value = _number(row.get(metric))
        if stamp is not None and value is not None and stamp >= end - seconds:
            values.append(value)
    return mean(values) if values else None


def _metric(kind: str, value: float, unit: str) -> dict[str, Any]:
    return {"kind": kind, "value": round(float(value), 3), "unit": unit}




# Derived test outputs that can participate in the profile's canonical metric
# resolver. The immutable test result remains the source of truth; this mapping
# only publishes an observation for existing Fitness calculations/sensors.
# ``metric`` is the Wellness-facing canonical key while ``evaluation_metric``
# is the established evaluation/history key where one already exists.
FITNESS_TEST_CANONICAL_METRICS: dict[str, dict[str, str | None]] = {
    "estimated_vo2max": {
        "metric": "vo2_max",
        "evaluation_metric": "vo2max",
        "method": "estimated",
    },
    "estimated_ftp": {
        "metric": "threshold_power",
        "evaluation_metric": "threshold_power",
        "method": "estimated",
    },
    "critical_power_estimate": {
        "metric": "critical_power",
        "evaluation_metric": None,
        "method": "estimated",
    },
    "critical_swim_speed": {
        "metric": "critical_swim_speed",
        "evaluation_metric": None,
        "method": "estimated",
    },
}


def fitness_test_metric_observations(
    result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return canonical metric observations published by one test result.

    This never mutates or replaces the persisted result. Consumers can select a
    current observation while the complete test result and every competing
    device/provider observation remain retained for provenance/history.
    """
    if not isinstance(result, dict):
        return []
    test_id = str(result.get("test_id") or "").strip()
    completed_at = str(result.get("completed_at") or "").strip()
    if not test_id or not completed_at:
        return []
    reference = (
        dict(result.get("reference") or {})
        if isinstance(result.get("reference"), dict)
        else {}
    )
    rows: list[dict[str, Any]] = []
    primary = result.get("primary")
    if isinstance(primary, dict):
        rows.append(primary)
    rows.extend(row for row in (result.get("metrics") or []) if isinstance(row, dict))

    observations: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row.get("kind") or "").strip()
        mapping = FITNESS_TEST_CANONICAL_METRICS.get(kind)
        value = _number(row.get("value"))
        if mapping is None or value is None:
            continue
        observations.append({
            "metric": mapping["metric"],
            "evaluation_metric": mapping["evaluation_metric"],
            "metric_kind": kind,
            "value": round(value, 3),
            "unit": row.get("unit"),
            "timestamp": completed_at,
            "source_type": "fitness_test",
            "source_id": f"fitness_test:{test_id}",
            "sources": [f"fitness_test:{test_id}"],
            "test_id": test_id,
            "test_result_id": f"{test_id}@{completed_at}",
            "method": mapping["method"],
            "reference": reference,
        })
    return observations

def _result(
    test_id: str,
    completed_at: str,
    *,
    primary: dict[str, Any] | None = None,
    metrics: list[dict[str, Any]] | None = None,
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "completed_at": completed_at,
        "status": "scored" if primary else "completed_unscored",
        "primary": primary,
        "metrics": list(metrics or []),
        "reference": dict(reference or {}),
    }


def calculate_fitness_test_result(
    prescription: dict[str, Any] | None,
    samples: list[dict[str, Any]],
    *,
    completed_at: str,
    age: int | None = None,
    sex: str | None = None,
    weight_kg: float | None = None,
) -> dict[str, Any] | None:
    """Return the persisted result for a completed built-in Fitness test.

    Results are deliberately limited to measurements that Fitness can derive from
    the live sensor timeline without asking the user to type a score after the
    fact. Tests requiring manually counted repetitions/load are persisted as
    completed-but-unscored rather than fabricating a value.
    """
    prescription = prescription if isinstance(prescription, dict) else {}
    if str(prescription.get("source") or "") != "fitness_test":
        return None
    test_id = str(prescription.get("id") or "")
    if not test_id:
        return None
    reference = prescription.get("reference") if isinstance(prescription.get("reference"), dict) else {}

    if test_id == "running_cooper_12min":
        rows = _step_samples(samples, 1)
        distance = _distance_m(rows)
        metrics: list[dict[str, Any]] = []
        if distance is not None and distance > 504.9:
            metrics.append(_metric("estimated_vo2max", (distance - 504.9) / 44.73, "mL/kg/min"))
        return _result(test_id, completed_at, primary=_metric("distance", distance, "m") if distance else None, metrics=metrics, reference=reference)

    if test_id == "running_5k_time_trial":
        rows = _step_samples(samples, 1)
        elapsed = _elapsed_seconds(rows)
        distance = _distance_m(rows)
        metrics = []
        if elapsed and distance and distance > 0:
            metrics.append(_metric("pace", elapsed / (distance / 1000.0), "s/km"))
        if distance:
            metrics.append(_metric("distance", distance, "m"))
        return _result(test_id, completed_at, primary=_metric("elapsed", elapsed, "s") if elapsed else None, metrics=metrics, reference=reference)

    if test_id == "running_5min_field":
        rows = _step_samples(samples, 1)
        distance = _distance_m(rows)
        metrics = []
        if distance:
            metrics.append(_metric("speed", distance / 1000.0 / (5.0 / 60.0), "km/h"))
        return _result(test_id, completed_at, primary=_metric("distance", distance, "m") if distance else None, metrics=metrics, reference=reference)

    if test_id == "cycling_ftp_20min":
        rows = _step_samples(samples, 3)
        avg_power = _mean_metric(rows, METRIC_POWER)
        metrics = []
        if avg_power:
            metrics.append(_metric("mean_power", avg_power, "W"))
        ftp = avg_power * 0.95 if avg_power else None
        return _result(test_id, completed_at, primary=_metric("estimated_ftp", ftp, "W") if ftp else None, metrics=metrics, reference=reference)

    if test_id == "cycling_5min_power":
        rows = _step_samples(samples, 3)
        avg_power = _mean_metric(rows, METRIC_POWER)
        metrics = []
        relative_power = None
        if avg_power:
            metrics.append(_metric("mean_power", avg_power, "W"))
            if weight_kg and weight_kg > 0:
                relative_power = avg_power / weight_kg
                metrics.append(_metric("relative_power", relative_power, "W/kg"))
                metrics.append(_metric("estimated_vo2max", 16.6 + 8.87 * relative_power, "mL/kg/min"))
        return _result(test_id, completed_at, primary=_metric("mean_power", avg_power, "W") if avg_power else None, metrics=metrics, reference=reference)

    if test_id == "cycling_3min_allout":
        rows = _step_samples(samples, 2)
        end_power = _last_seconds_mean(rows, METRIC_POWER, 30.0)
        avg_power = _mean_metric(rows, METRIC_POWER)
        metrics = []
        if avg_power:
            metrics.append(_metric("mean_power", avg_power, "W"))
        return _result(test_id, completed_at, primary=_metric("critical_power_estimate", end_power, "W") if end_power else None, metrics=metrics, reference=reference)

    if test_id == "walking_6min":
        rows = _step_samples(samples, 1)
        distance = _distance_m(rows)
        return _result(test_id, completed_at, primary=_metric("distance", distance, "m") if distance else None, reference=reference)

    if test_id == "walking_rockport_1mile":
        rows = _step_samples(samples, 1)
        elapsed = _elapsed_seconds(rows)
        finish_hr = _last_metric(rows, METRIC_HEART_RATE)
        metrics = []
        if finish_hr:
            metrics.append(_metric("finish_heart_rate", finish_hr, "bpm"))
        vo2 = None
        sex_code = 1.0 if str(sex or "").lower() == "male" else 0.0 if str(sex or "").lower() == "female" else None
        if elapsed and finish_hr and age is not None and weight_kg and weight_kg > 0 and sex_code is not None:
            weight_lb = weight_kg * 2.2046226218
            time_min = elapsed / 60.0
            vo2 = 132.853 - 0.0769 * weight_lb - 0.3877 * age + 6.315 * sex_code - 3.2649 * time_min - 0.1565 * finish_hr
            metrics.append(_metric("estimated_vo2max", vo2, "mL/kg/min"))
        return _result(test_id, completed_at, primary=_metric("elapsed", elapsed, "s") if elapsed else None, metrics=metrics, reference=reference)

    if test_id == "rowing_2k":
        rows = _step_samples(samples, 1)
        elapsed = _elapsed_seconds(rows)
        metrics = []
        if elapsed:
            metrics.append(_metric("pace_500m", elapsed / 4.0, "s/500m"))
        return _result(test_id, completed_at, primary=_metric("elapsed", elapsed, "s") if elapsed else None, metrics=metrics, reference=reference)

    if test_id == "swimming_css":
        rows_400 = _step_samples(samples, 1)
        rows_200 = _step_samples(samples, 3)
        t400 = _elapsed_seconds(rows_400)
        t200 = _elapsed_seconds(rows_200)
        metrics = []
        if t400:
            metrics.append(_metric("time_400m", t400, "s"))
        if t200:
            metrics.append(_metric("time_200m", t200, "s"))
        css = 200.0 / (t400 - t200) if t400 and t200 and t400 > t200 else None
        primary = None
        if css and css > 0:
            primary = _metric("css_pace", 100.0 / css, "s/100m")
            metrics.append(_metric("critical_swim_speed", css, "m/s"))
        return _result(test_id, completed_at, primary=primary, metrics=metrics, reference=reference)

    if test_id == "strength_plank_hold":
        elapsed = _elapsed_seconds(_step_samples(samples, 1))
        return _result(test_id, completed_at, primary=_metric("elapsed", elapsed, "s") if elapsed else None, reference=reference)

    # The current live sensor model does not reliably know the external load and
    # accepted repetitions for the Brzycki set or manually judged push-up count.
    return _result(test_id, completed_at, reference=reference)

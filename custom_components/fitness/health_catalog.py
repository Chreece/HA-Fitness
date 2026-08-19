"""Canonical vendor-neutral health and fitness measurement catalog."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class HealthMetricSpec:
    key: str
    category: str
    unit: str | None = None


HEALTH_METRICS = {spec.key: spec for spec in (
    HealthMetricSpec("heart_rate", "cardiovascular", "bpm"),
    HealthMetricSpec("resting_heart_rate", "cardiovascular", "bpm"),
    HealthMetricSpec("min_heart_rate", "cardiovascular", "bpm"),
    HealthMetricSpec("max_heart_rate", "cardiovascular", "bpm"),
    HealthMetricSpec("hrv_ms", "cardiovascular", "ms"),
    HealthMetricSpec("respiratory_rate", "cardiovascular", "breaths/min"),
    HealthMetricSpec("spo2", "oxygen", "%"),
    HealthMetricSpec("skin_temperature", "temperature", "°C"),
    HealthMetricSpec("skin_temperature_min", "temperature", "°C"),
    HealthMetricSpec("skin_temperature_max", "temperature", "°C"),
    HealthMetricSpec("body_temperature", "temperature", "°C"),
    HealthMetricSpec("device_temperature", "temperature", "°C"),
    HealthMetricSpec("steps", "activity", "steps"),
    HealthMetricSpec("distance_m", "activity", "m"),
    HealthMetricSpec("calories", "activity", "kcal"),
    HealthMetricSpec("active_minutes", "activity", "min"),
    HealthMetricSpec("activity_level", "activity"),
    HealthMetricSpec("stress", "activity"),
    HealthMetricSpec("weight", "body_composition", "kg"),
    HealthMetricSpec("bmi", "body_composition"),
    HealthMetricSpec("body_fat", "body_composition", "%"),
    HealthMetricSpec("body_water", "body_composition", "%"),
    HealthMetricSpec("muscle_mass", "body_composition", "kg"),
    HealthMetricSpec("bone_mass", "body_composition", "kg"),
    HealthMetricSpec("battery", "device_state", "%"),
    HealthMetricSpec("charging", "device_state"),
    HealthMetricSpec("wear_state", "device_state"),
)}

ALIASES = {
    "max_hr": "max_heart_rate",
    "min_hr": "min_heart_rate",
    "hrv": "hrv_ms",
    "activity_minutes": "active_minutes",
    "weight_kg": "weight",
    "body_fat_percent": "body_fat",
    "body_water_percent": "body_water",
    "muscle_mass_kg": "muscle_mass",
    "bone_mass_kg": "bone_mass",
}

DEVICE_CONTEXT_FIELDS = frozenset({"measurement_context", "wear_state", "charging"})

def canonical_metric_key(value: str) -> str:
    key = str(value or "").strip().lower()
    return ALIASES.get(key, key)

def metric_spec(value: str) -> HealthMetricSpec | None:
    return HEALTH_METRICS.get(canonical_metric_key(value))

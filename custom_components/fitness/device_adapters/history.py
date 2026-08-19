"""Vendor-neutral direct-device longitudinal history contracts.

These types let physical-device adapters import wellness history without
pretending every device stores FIT workouts.  Transport/protocol code stays in
``device_adapters`` while profile persistence remains owned by ``FitnessManager``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..providers.sleep import SleepRecord

MAX_DEVICE_METRIC_POINTS = 2048
MAX_DEVICE_SLEEP_RECORDS = 32
MAX_POINT_CONTEXT_ITEMS = 12


@dataclass(slots=True, frozen=True)
class DeviceMetricPoint:
    """One bounded longitudinal metric observation from a physical device."""

    metric: str
    value: float
    timestamp: str
    source_type: str
    source_entity: str | None = None
    sources: tuple[str, ...] = ()
    context: tuple[tuple[str, Any], ...] = ()


@dataclass(slots=True, frozen=True)
class DeviceHistoryBatch:
    """A bounded direct-device history import transaction."""

    metric_points: tuple[DeviceMetricPoint, ...] = ()
    sleep_records: tuple[SleepRecord, ...] = ()

    @classmethod
    def bounded(
        cls,
        *,
        metric_points: Iterable[DeviceMetricPoint] = (),
        sleep_records: Iterable[SleepRecord] = (),
    ) -> "DeviceHistoryBatch":
        """Create a hard-bounded batch so a device cannot grow profile work."""
        return cls(
            metric_points=tuple(metric_points)[:MAX_DEVICE_METRIC_POINTS],
            sleep_records=tuple(sleep_records)[:MAX_DEVICE_SLEEP_RECORDS],
        )

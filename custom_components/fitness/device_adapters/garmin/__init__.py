"""Garmin local Bluetooth workout archive support.

Keep package initialization protocol-only.  File/export providers reuse Garmin's
vendor-neutral bounded FIT decoder, and importing that decoder must not eagerly
load Home Assistant Bluetooth/issue-registry dependencies.  Heavy coordinator
and adapter objects remain lazily available through the historical package API.
"""
from __future__ import annotations

from .protocol import (
    GARMIN_ADVERTISEMENT_SERVICE_UUID,
    GARMIN_COMPANY_ID,
    GARMIN_GFDI_V0_SERVICE_UUID,
    GARMIN_GFDI_V1_SERVICE_UUID,
    GARMIN_GFDI_V2_SERVICE_UUID,
    garmin_advertisement_identity,
)

__all__ = [
    "ARCHIVE_ADAPTER",
    "GARMIN_ADVERTISEMENT_SERVICE_UUID",
    "GARMIN_COMPANY_ID",
    "GARMIN_GFDI_V0_SERVICE_UUID",
    "GARMIN_GFDI_V1_SERVICE_UUID",
    "GARMIN_GFDI_V2_SERVICE_UUID",
    "GarminLocalCoordinator",
    "garmin_advertisement_identity",
]


def __getattr__(name: str):
    """Load Home Assistant-dependent Garmin objects only when requested."""
    if name == "GarminLocalCoordinator":
        from .coordinator import GarminLocalCoordinator

        return GarminLocalCoordinator
    if name == "ARCHIVE_ADAPTER":
        from .adapter import ARCHIVE_ADAPTER

        return ARCHIVE_ADAPTER
    raise AttributeError(name)

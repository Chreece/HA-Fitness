"""Regression tests for conjunctive live-device catalog matching."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components/fitness/live/device_identity.py"


def _identity_module():
    spec = importlib.util.spec_from_file_location("fitness_device_identity_contract", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Endpoint:
    def __init__(self, metadata=None):
        self.metadata = dict(metadata or {})


def test_transport_plus_name_prefix_is_conjunctive():
    identity = _identity_module()
    anonymous_bluetooth = {"bluetooth": _Endpoint()}
    named_bluetooth = {"bluetooth": _Endpoint({"advertised_name": "M1_98C6"})}

    # A stale persisted/display name alone must not resurrect a removed product.
    assert identity.catalog_product_id("M1_98C6", anonymous_bluetooth) is None
    # Current endpoint evidence can still satisfy the same catalog rule.
    assert (
        identity.catalog_product_id("M1_98C6", named_bluetooth)
        == "cycplus_m1_gps_bike_computer"
    )
    s3_bluetooth = {"bluetooth": _Endpoint({"advertised_name": "CYCPLUS S3 29308"})}
    random_bluetooth = {"bluetooth": _Endpoint({"advertised_name": "Random Bluetooth Device"})}
    assert (
        identity.catalog_product_id("CYCPLUS S3 29308", s3_bluetooth)
        != "cycplus_m1_gps_bike_computer"
    )
    assert identity.catalog_product_id("Random Bluetooth Device", random_bluetooth) is None


def test_name_prefix_rule_does_not_ignore_required_transport():
    identity = _identity_module()

    # The M1 catalog has a Bluetooth + M1_ rule.  A matching-looking name on a
    # non-Bluetooth route must not satisfy that combined rule.
    assert identity.catalog_product_id("M1_98C6", {"antplus": _Endpoint()}) is None


def test_protocol_identity_rules_still_match():
    identity = _identity_module()
    ant = {"antplus": _Endpoint({"manufacturer_id": 95})}
    assert identity.catalog_product_id("Power Meter", ant) == "stryd_running_power_meter"

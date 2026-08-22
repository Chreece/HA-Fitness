"""Regression tests for bounded Home Assistant Bluetooth cache replay."""
from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BT_PATH = ROOT / "custom_components/fitness/live/bluetooth.py"
BT = BT_PATH.read_text(encoding="utf-8")
TREE = ast.parse(BT)


def _method_node(name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in TREE.body:
        if not isinstance(node, ast.ClassDef) or node.name != "BluetoothFitnessProvider":
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                return item
    raise AssertionError(f"method {name!r} not found")


def _method_source(name: str) -> str:
    node = _method_node(name)
    return ast.get_source_segment(BT, node) or ""


def _standalone_method(name: str):
    """Compile one provider method without importing Home Assistant."""
    node = _method_node(name)
    function = ast.FunctionDef(
        name=name,
        args=node.args,
        body=node.body,
        decorator_list=[],
        returns=node.returns,
        type_comment=node.type_comment,
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {
        "math": math,
        "DISCOVERY_CACHE_MAX_AGE": 60.0,
        "DISCOVERY_CACHE_FUTURE_TOLERANCE": 5.0,
    }
    exec(compile(module, str(BT_PATH), "exec"), namespace)
    return namespace[name]


def test_cached_bluetooth_replay_uses_original_ha_observation_time():
    fresh = _standalone_method("_cached_discovery_is_fresh")
    self = SimpleNamespace()

    assert fresh(self, SimpleNamespace(time=940.0), 1000.0) is True
    assert fresh(self, SimpleNamespace(time=939.999), 1000.0) is False


def test_cached_bluetooth_replay_rejects_unknown_invalid_and_wrong_clock_times():
    fresh = _standalone_method("_cached_discovery_is_fresh")
    self = SimpleNamespace()

    assert fresh(self, SimpleNamespace(), 1000.0) is False
    assert fresh(self, SimpleNamespace(time="not-a-time"), 1000.0) is False
    assert fresh(self, SimpleNamespace(time=float("nan")), 1000.0) is False
    assert fresh(self, SimpleNamespace(time=1006.0), 1000.0) is False
    # Tiny scheduling/clock-reading skew is harmless and should not hide a live route.
    assert fresh(self, SimpleNamespace(time=1003.0), 1000.0) is True


def test_cache_freshness_guard_runs_before_normal_discovery_callback():
    replay = _method_source("_replay_cached_discovery")
    guard = "self._cached_discovery_is_fresh(info, now_mono)"
    dispatch = "self._async_discovered(info, None)"

    assert "now_mono = self.hass.loop.time()" in replay
    assert guard in replay
    assert dispatch in replay
    assert replay.index(guard) < replay.index(dispatch)
    assert "DISCOVERY_CACHE_REPLAY_LIMIT" in replay
    assert "DISCOVERY_CACHE_SCAN_LIMIT" in replay


def test_cache_freshness_policy_is_transport_generic():
    helper = _method_source("_cached_discovery_is_fresh")
    replay = _method_source("_replay_cached_discovery")
    policy = helper + replay

    assert "BluetoothServiceInfoBleak.time" in helper
    assert "CYCPLUS" not in policy
    assert "M1_" not in policy
    assert "Garmin" not in policy
    assert "Stryd" not in policy


def test_startup_cache_replay_cannot_create_unknown_physical_sensor():
    replay = _method_source("_replay_cached_discovery")
    known = _method_source("_cached_discovery_known_endpoint")

    assert 'self.runtime.endpoint_aliases.get(f"bluetooth:{address}")' in known
    assert "canonical_id in self.runtime.sensors" in known
    assert "known_endpoint = self._cached_discovery_known_endpoint(info)" in replay
    assert "if allow_new_since is None:" in replay
    assert "unknown_startup += 1" in replay
    assert replay.index("if allow_new_since is None:") < replay.index("self._async_discovered(info, None)")


def test_explicit_active_scan_only_unlocks_new_cache_records_from_scan_window():
    replay = _method_source("_replay_cached_discovery")
    refresh = _method_source("async_refresh_discovery")

    assert "allow_new_since: float | None = None" in refresh
    assert "scan_started = self.hass.loop.time()" in refresh
    assert "allow_new_since = scan_started" in refresh
    assert "self._cache_replay_allow_new_since = allow_new_since" in refresh
    assert "self._replay_cached_discovery()" in refresh
    assert "self._cache_replay_allow_new_since = None" in refresh
    assert "DISCOVERY_CACHE_SCAN_START_TOLERANCE" in replay
    assert "observed_value < (" in replay
    assert "float(allow_new_since)" in replay


def test_startup_cache_policy_remains_vendor_neutral():
    policy = _method_source("_cached_discovery_known_endpoint") + _method_source("_replay_cached_discovery")
    assert "CYCPLUS" not in policy
    assert "M1_" not in policy
    assert "Garmin" not in policy
    assert "Stryd" not in policy

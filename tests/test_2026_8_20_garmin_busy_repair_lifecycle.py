"""Regression contracts for transient Garmin Bluetooth-host contention."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GARMIN_PATH = ROOT / "custom_components" / "fitness" / "device_adapters" / "garmin" / "coordinator.py"
GARMIN = GARMIN_PATH.read_text(encoding="utf-8")


def _method(name: str) -> str:
    tree = ast.parse(GARMIN)
    lines = GARMIN.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(name)


def test_startup_clears_legacy_connection_busy_repairs():
    setup = _method("async_setup")
    assert 'action="bluetooth_connection_busy"' in setup
    assert "for stored_sensor_id in tuple" in setup
    assert "resolve_sensor_id(raw_sensor_id)" in setup


def test_background_phone_contention_does_not_create_persistent_repair():
    sync = _method("_async_sync")
    branch = sync.split("if active_host_contention:", 1)[1].split("elif recent_partial", 1)[0]
    assert "if manual_request:" in branch
    assert "self._report_connection_busy(sensor_id)" in branch
    assert "else:" in branch
    assert "self._clear_connection_busy_issue(sensor_id)" in branch


def test_removing_or_unassigning_garmin_clears_busy_repair_too():
    acceptance = _method("acceptance_changed")
    assignment = _method("assignment_changed")
    forget = _method("forget_sensor")
    assert "_clear_connection_busy_issue(sensor_id)" in acceptance
    assert "_clear_connection_busy_issue(sensor_id)" in assignment
    assert "_clear_connection_busy_issue(sensor_id)" in forget

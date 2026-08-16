"""Regression tests for Fitness TV websocket registration integrity."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TV_DASHBOARD = ROOT / "custom_components" / "fitness" / "tv_dashboard.py"


def test_every_registered_tv_websocket_handler_exists() -> None:
    """A stale registration must never prevent the Fitness config entry loading."""
    module = ast.parse(TV_DASHBOARD.read_text(encoding="utf-8"))
    definitions = {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    registered: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "async_register_command" or len(node.args) < 2:
            continue
        handler = node.args[1]
        if isinstance(handler, ast.Name):
            registered.append(handler.id)

    missing = sorted(set(registered) - definitions)
    assert not missing, f"Undefined Fitness TV websocket handlers registered: {missing}"


def test_removed_ma_pair_command_is_not_registered() -> None:
    source = TV_DASHBOARD.read_text(encoding="utf-8")
    assert "websocket_tv_music_ma_pair" not in source

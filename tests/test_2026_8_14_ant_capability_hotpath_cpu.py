"""Repeated ANT telemetry must avoid capability and callback amplification."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPS = (ROOT / "custom_components/fitness/live/antplus_core/capabilities.py").read_text()
RECEIVER = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_record_observed_page_does_not_resolve_capabilities():
    block = CAPS.split("def record_observed_page", 1)[1].split(
        "def record_fe_command_status", 1
    )[0]
    assert "capability_snapshot(" not in block
    assert "if page in pages:" in block


def test_repeated_pages_skip_capability_signature():
    block = RECEIVER.split("new_capability_page = record_observed_page", 1)[0]
    tail = block.rsplit("# Repeated ANT pages", 1)[1]
    assert "page_is_new" in tail
    assert "capability_signature(device) if page_is_new else None" in tail


def test_metric_callback_is_once_per_packet_not_once_per_metric():
    block = RECEIVER.split('self.diagnostics.inc("metrics_changed"', 1)[1].split(
        "def _decode_metadata", 1
    )[0]
    assert "if changed_metrics:" in block
    assert "for key in changed_metrics:" not in block
    assert "key = changed_metrics[-1]" in block


def test_raw_protocol_event_path_rejects_telemetry_before_capability_snapshot():
    block = ANT.split("def _schedule_protocol_event", 1)[1].split(
        "def _emit_raw_protocol_events", 1
    )[0]
    guard = block.index("if device_type not in (16, 115):")
    snap = block.index("snapshot = capability_snapshot(device)")
    assert guard < snap

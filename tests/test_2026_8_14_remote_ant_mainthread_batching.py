"""Remote ANT RF events must do constant-time MainThread work."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = (
    ROOT / "custom_components/fitness/live/antplus_core/remote.py"
).read_text(encoding="utf-8")


def test_remote_event_handler_has_no_per_packet_loop():
    block = REMOTE.split("def handle_packet_event", 1)[1].split(
        "def handle_gateway_hello", 1
    )[0]
    assert "packet_worker.enqueue_batch(gateway_id, packets)" in block
    assert "for packet in packets" not in block
    assert "update_remote_capture_state" not in block
    assert "_remote_packet_key" not in block
    assert "_remote_packet_is_event" not in block


def test_packet_classification_and_copying_are_worker_side():
    ingest = REMOTE.split("def _ingest_packet", 1)[1].split(
        "def _take_incoming", 1
    )[0]
    assert "dict(packet)" in ingest
    assert "_remote_packet_is_event(packet)" in ingest
    assert "_remote_packet_key(gateway_id, packet)" in ingest


def test_mainthread_batch_inbox_is_bounded():
    enqueue = REMOTE.split("def enqueue_batch", 1)[1].split(
        "def enqueue(", 1
    )[0]
    assert "REMOTE_INPUT_BATCH_QUEUE_MAX" in enqueue
    assert "self._incoming.popleft()" in enqueue
    assert "self._wake.set()" in enqueue


def test_worker_drains_batches_before_decode():
    run = REMOTE.split("def _run", 1)[1].split(
        "def _parse_adapters", 1
    )[0]
    assert "batches = self._take_incoming()" in run
    assert "for gateway_id, packets in batches:" in run
    assert "self._ingest_packet(gateway_id, packet)" in run
    assert "for item in telemetry:" in run


def test_rf_packets_do_not_confirm_capture_state():
    handler = REMOTE.split("def handle_packet_event", 1)[1].split(
        "def handle_gateway_hello", 1
    )[0]
    assert "update_remote_capture_state" not in handler
    # Explicit status/control paths still own capture confirmation.
    rest = REMOTE.split("def handle_gateway_hello", 1)[1]
    assert "update_remote_capture_state" in rest

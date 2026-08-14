from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ant_receiver_has_pre_diagnostics_idle_ingress_gate():
    text = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
    block = text[text.index("    def process_packet("):text.index("    def _metadata_candidate(")]
    assert block.index("fast_ignore_idle_packet") < block.index('diagnostics.inc("receiver_packets_seen")')
    local = text[text.index("    def _on_data("):text.index("    def _expire_discovery_candidates(")]
    assert local.index("fast_ignore_idle_packet") < local.index("payload = bytes(data[:8])")


def test_remote_ant_bus_filters_accepted_idle_before_worker_queue():
    text = (ROOT / "custom_components/fitness/live/antplus_core/remote.py").read_text()
    block = text[text.index("    def handle_packet_event"):text.index("    @callback\n    def handle_gateway_hello")]
    assert block.index("fast_ignore_idle_packet") < block.index("packet_worker.enqueue_batch")


def test_fitness_has_out_of_band_event_loop_stall_watchdog():
    text = (ROOT / "custom_components/fitness/live/stall_watchdog.py").read_text()
    assert "sys._current_frames()" in text
    assert "FITNESS_STALL_DETECTED" in text
    assert "fitness-event-loop-watchdog" in text

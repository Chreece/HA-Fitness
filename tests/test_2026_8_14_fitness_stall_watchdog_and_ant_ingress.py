from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ant_receiver_has_pre_diagnostics_bounded_idle_ingress_gate():
    text = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
    block = text[text.index("    def process_packet("):text.index("    def _metadata_candidate(")]
    assert block.index("fast_ignore_idle_packet") < block.index('diagnostics.inc("receiver_packets_seen")')
    assert "IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS = 0.5" in text
    # Sampling is consumed exactly once inside process_packet. Local transport must
    # not consume the same idle slot before handing the packet to the receiver.
    local = text[text.index("    def _on_data("):text.index("    def _expire_discovery_candidates(")]
    assert "fast_ignore_idle_packet" not in local
    assert "self.process_packet(" in local


def test_remote_ant_single_packet_is_sampled_once_before_worker_queue():
    text = (ROOT / "custom_components/fitness/live/antplus_core/remote.py").read_text()
    block = text[text.index("    def handle_packet_event"):text.index("    @callback\n    def handle_gateway_hello")]
    assert block.index("fast_ignore_idle_packet") < block.index("packet_worker.enqueue_batch")
    assert "page = _remote_packet_page(packet)" in block
    assert "ingress_checked=ingress_checked" in block
    # Multi-packet batches are not walked on HA's MainThread.
    assert "for packet in packets" not in block

    decode = text[text.index("    def _decode_item"):text.index("    def _run", text.index("    def _decode_item"))]
    assert "ingress_checked=ingress_checked" in decode


def test_fitness_has_out_of_band_event_loop_stall_watchdog():
    text = (ROOT / "custom_components/fitness/live/stall_watchdog.py").read_text()
    assert "sys._current_frames()" in text
    assert "FITNESS_STALL_DETECTED" in text
    assert "fitness-event-loop-watchdog" in text
    assert "CoreState.running" in text
    assert "_stack_is_home_assistant_shutdown" in text
    assert "FITNESS_STALL_OBSERVED_EXTERNAL" in text
    assert "if not self._stack_is_fitness_owned(main_stack):" in text

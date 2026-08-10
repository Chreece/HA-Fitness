from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_failover_is_per_metric_and_sticky():
    assert "def _switch_live_source_if_needed" in MANAGER
    block = MANAGER[
        MANAGER.index("def _switch_live_source_if_needed"):
        MANAGER.index("def live_values", MANAGER.index("def _switch_live_source_if_needed"))
    ]
    assert "if current is not None and source_is_usable" in block
    assert "for candidate in candidates:" in block
    assert "self._live_sources_cache[metric] = candidate" in block


def test_candidates_are_reranked_only_at_workout_start():
    start = MANAGER.index("def _begin_session_from_live_data")
    block = MANAGER[start:start+2400]
    assert "discover_candidates(" in block
    assert "self._live_source_switches = []" in block


def test_source_switches_are_recorded_and_diagnosable():
    assert '"metric": metric' in MANAGER
    assert '"from": previous' in MANAGER
    assert '"to": candidate.entity_id' in MANAGER
    assert "def live_source_info" in MANAGER
    assert '"fallback_active"' in MANAGER
    assert '"source_switch_count"' in MANAGER


def test_metrics_can_use_different_devices():
    start = MANAGER.index("def live_values")
    end = MANAGER.index("def live_sources", start)
    block = MANAGER[start:end]
    assert "for metric in (" in block
    assert "_switch_live_source_if_needed(metric)" in block

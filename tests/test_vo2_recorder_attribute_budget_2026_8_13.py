from pathlib import Path

S = Path("custom_components/fitness/sensor.py").read_text()


def test_vo2_daily_series_is_compact_and_bounded_for_recorder():
    block = S[S.index('"cardiorespiratory_fitness_trend": {'):S.index('"training_load": {')]
    assert '(recorder.get("vo2max_daily") or [])[-90:]' in block
    assert '"start": item.get("start") or item.get("date")' in block
    assert '"value": item.get("value")' in block
    assert '"daily_series": recorder.get("vo2max_daily") or []' not in block

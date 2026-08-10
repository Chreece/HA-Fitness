from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")
SENSOR = (
    ROOT / "custom_components/fitness/sensor.py"
).read_text(encoding="utf-8")
EXPLANATIONS = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")


def test_every_evaluation_sensor_attaches_provenance():
    assert "provenance = self.manager.localized_evaluation_provenance(m)" in SENSOR
    assert "base_explanation.update(provenance)" in SENSOR


def test_provenance_exposes_formula_and_concrete_inputs():
    start = MANAGER.index("def evaluation_provenance")
    end = MANAGER.index("def evaluation(", start)
    block = MANAGER[start:end]
    assert '"formula"' in block
    assert '"input_sources"' in block
    assert '"entity_id"' in MANAGER
    assert '"raw_value"' in MANAGER
    assert '"raw_unit"' in MANAGER


def test_hr_reserve_shows_real_inputs_and_formula():
    block = MANAGER[
        MANAGER.index('if metric == "heart_rate_reserve"'):
        MANAGER.index('if metric == "vo2max"')
    ]
    assert "maximum_hr − resting_hr" in block
    assert 'evaluation_provenance("max_hr")' in block
    assert 'evaluation_provenance("resting_hr")' in block


def test_threshold_pace_explains_mps_to_min_per_km_conversion():
    start = MANAGER.index('if metric == "threshold_pace"')
    block = MANAGER[start:start+1800]
    assert "1000 / threshold_speed_m_s / 60" in block
    assert 'provider_item("threshold_speed"' in block


def test_vo2max_identifies_direct_source_or_uth_formula():
    start = MANAGER.index('if metric == "vo2max"')
    block = MANAGER[start:start+2200]
    assert 'provider_item("vo2max"' in block
    assert "15.3 × maximum_hr / resting_hr" in block


def test_friend_formula_is_exactly_exposed():
    start = MANAGER.index('if metric == "friend_predicted_vo2max"')
    block = MANAGER[start:start+1700]
    assert "79.9 − 0.39×age − 13.7×gender" in block
    assert "0.127×weight_lb" in block


def test_provider_metrics_do_not_claim_fitness_formula():
    for metric in (
        "fitness_age",
        "training_readiness",
        "sleep_score",
        "provider_training_status",
    ):
        assert f'"{metric}"' in MANAGER
    assert "provider algorithm may be proprietary" in MANAGER


def test_long_term_metrics_state_window_and_aggregation():
    assert "previous 7 days" in MANAGER
    assert "previous 28 days" in MANAGER
    assert "previous 42 days" in MANAGER
    assert "previous 90 days" in MANAGER
    assert "fitness_merged_workout_history" in MANAGER


def test_explanation_module_remains_ai_free():
    lowered = EXPLANATIONS.lower()
    for forbidden in (
        "_call_ai",
        "conversation.process",
        "ai_task.generate_data",
        "services.async_call",
    ):
        assert forbidden not in lowered

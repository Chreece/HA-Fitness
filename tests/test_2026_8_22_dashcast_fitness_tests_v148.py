from pathlib import Path

from custom_components.fitness.const import METRIC_DISTANCE, METRIC_POWER
from custom_components.fitness.fitness_test_results import calculate_fitness_test_result
from custom_components.fitness.workout_prescriptions import fitness_test, fitness_test_catalog

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def test_dashcast_bootstrap_completes_existing_server_reservation_instead_of_rearming():
    block = ACCOUNTS[ACCOUNTS.index("class FitnessDashCastBootstrapView"):ACCOUNTS.index("class FitnessPortalLoginView")]
    assert 'target_entity_id.startswith("media_player.")' in block
    assert 'descriptor.get("mode") == "server"' in block
    assert "hub.cast_target(profile_entry_id) == target_entity_id" in block
    server_branch = block[block.index('if target_entity_id.startswith("media_player.")'):block.index('elif descriptor.get("busy")')]
    assert "expect_local_cast" not in server_branch


def test_browser_tv_prereservation_is_same_attempt_and_races_are_not_http_500():
    block = ACCOUNTS[ACCOUNTS.index("class FitnessDashCastBootstrapView"):ACCOUNTS.index("class FitnessPortalLoginView")]
    assert 'elif descriptor.get("busy")' in block
    assert 'descriptor.get("mode") == "browser"' in block
    assert 'expected_source == f"browser-launch:{launch_entity_id}"' in block
    assert "except ValueError as err:" in block
    assert "raise web.HTTPConflict" in block
    assert "Another Fitness Cast is already active" in block


def test_profile_cast_controls_share_one_three_state_contract():
    assert "const _fitnessCastControlState" in FRONTEND
    assert 'state === "connected"' in FRONTEND
    assert 'state === "connecting"' in FRONTEND
    assert "button.disabled = cast.connecting" in FRONTEND
    assert "buttonLabel.textContent = active ? l.cast_stop" in FRONTEND
    assert "localToggle.disabled = pending" in FRONTEND
    assert "label.textContent = connected ? l.cast_stop" in FRONTEND
    assert "if (this._castState === \"connected\") { void this._stopCurrentCast(); return; }" in FRONTEND
    assert "if (this._castState === \"connecting\") return;" in FRONTEND


def test_every_fitness_test_has_a_https_study_reference_and_sports_are_grouped():
    tests = fitness_test_catalog("en")
    assert len(tests) >= 13
    assert {test["sport"] for test in tests} >= {"running", "cycling", "walking", "rowing", "swimming", "strength"}
    for test in tests:
        reference = test.get("reference") or {}
        assert reference.get("title")
        assert str(reference.get("url") or "").startswith("https://")
    assert 'const sportOrder=["running","cycling","walking","rowing","swimming","strength"]' in FRONTEND
    assert 'class="sport-tests"' in FRONTEND
    assert 'class="test-title" href="${_fitnessEscape(reference.url)}" target="_blank"' in FRONTEND


def test_completed_cooper_test_returns_distance_and_vo2_result():
    prescription = fitness_test("running_cooper_12min", "en")
    samples = [
        {"_prescription_step": 1, "_timestamp_epoch": 0.0, METRIC_DISTANCE: 2.0},
        {"_prescription_step": 1, "_timestamp_epoch": 720.0, METRIC_DISTANCE: 4.8},
    ]
    result = calculate_fitness_test_result(prescription, samples, completed_at="2026-08-22T20:00:00+00:00")
    assert result is not None
    assert result["status"] == "scored"
    assert result["primary"]["kind"] == "distance"
    assert result["primary"]["value"] == 2800.0
    vo2 = next(metric for metric in result["metrics"] if metric["kind"] == "estimated_vo2max")
    assert 51 < vo2["value"] < 52


def test_completed_ftp_test_returns_95_percent_of_twenty_minute_mean_power():
    prescription = fitness_test("cycling_ftp_20min", "en")
    samples = [
        {"_prescription_step": 3, "_timestamp_epoch": 0.0, METRIC_POWER: 300.0},
        {"_prescription_step": 3, "_timestamp_epoch": 1200.0, METRIC_POWER: 300.0},
    ]
    result = calculate_fitness_test_result(prescription, samples, completed_at="2026-08-22T20:00:00+00:00")
    assert result is not None
    assert result["primary"] == {"kind": "estimated_ftp", "value": 285.0, "unit": "W"}


def test_manual_strength_tests_are_persisted_as_completed_without_fake_score():
    result = calculate_fitness_test_result(
        fitness_test("strength_pushups_2min", "en"),
        [{"_prescription_step": 1, "_timestamp_epoch": 0.0}, {"_prescription_step": 1, "_timestamp_epoch": 120.0}],
        completed_at="2026-08-22T20:00:00+00:00",
    )
    assert result is not None
    assert result["status"] == "completed_unscored"
    assert result["primary"] is None


def test_fitness_test_result_is_persisted_during_workout_finalize_not_rpe_edit():
    rpe = MANAGER[MANAGER.index("def _apply_user_rpe_override"):MANAGER.index("async def async_set_workout_rpe")]
    finalize = MANAGER[MANAGER.index("def _finalize_local_workout"):MANAGER.index("def workout_retention_days")]
    assert "calculate_fitness_test_result" not in rpe
    assert "calculate_fitness_test_result" in finalize
    assert 'workout.extra["fitness_test_result"] = result' in finalize
    assert 'workout.extra["fitness_test_id"]' in finalize


def test_fitness_tests_card_consumes_persisted_results_and_refreshes_them():
    block = FRONTEND[FRONTEND.index("class FitnessTestsCard"):FRONTEND.index('customElements.define("fitness-tests-card"')]
    assert "this._results=r?.results" in block
    assert "fitness_test_latest_result" in block
    assert "fitness_test_manual_result" in block
    assert "Date.now()-this._testsLoadedAt>15000" in block
    assert "_resultMarkup" in block

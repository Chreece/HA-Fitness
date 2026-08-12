from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"
MANAGER = (FITNESS / "manager.py").read_text(encoding="utf-8")
DASHBOARD = (FITNESS / "dashboard.py").read_text(encoding="utf-8")
JS = (FITNESS / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
FEEDBACK = (FITNESS / "feedback.py").read_text(encoding="utf-8")
WORKOUTS = (FITNESS / "providers" / "workouts.py").read_text(encoding="utf-8")


def test_live_capture_is_provisional_for_provider_merge():
    assert 'a_live = a.source == "fitness_live_capture"' in WORKOUTS
    assert 'b_live = b.source == "fitness_live_capture"' in WORKOUTS
    assert 'return a_live != b_live' in WORKOUTS
    assert 'provider identity fields are authoritative' in WORKOUTS
    assert 'merged.sport = explicit.sport' in WORKOUTS
    assert 'merged.name = explicit.name' in WORKOUTS


def test_live_sport_inference_is_conservative():
    start = MANAGER.index("def _infer_sport")
    end = MANAGER.index("def _workout_name", start)
    block = MANAGER[start:end]
    assert '"cadence"' not in block
    assert 'return "Workout"' in block
    assert '"stryd"' in block
    assert '"cycling"' in block


def test_stale_route_is_rejected_against_latest_workout_identity():
    assert "def _route_matches_latest_workout" in DASHBOARD
    assert "route_names and workout_name and workout_name not in route_names" in DASHBOARD
    assert "workout_ids.isdisjoint(route_ids)" in DASHBOARD


def test_workout_card_keeps_metrics_even_with_route():
    start = JS.index("class FitnessWorkoutCard")
    end = JS.index("class FitnessSleepRecoveryCard", start)
    block = JS[start:end]
    assert 'const children = [this._mount("fitness-workout-highlights-card")]' in block
    assert 'children.push(this._mount("fitness-route-card"' in block


def test_live_card_uses_all_available_live_device_entities_only():
    assert '"live_entity_keys"' in DASHBOARD
    start = JS.index("class FitnessLiveWorkoutCard")
    end = JS.index("class FitnessWorkoutRpeCard", start)
    block = JS[start:end]
    assert "this._profile.live_entity_keys" in block
    assert '["unavailable","unknown"].includes(state.state)' in block
    assert 'key !== "workout_room"' in block
    assert "session_rpe" not in block


def test_optical_zone_palette_matches_requested_colors():
    for key in ("under_zone_1", "zone_1", "zone_2", "zone_3", "zone_4", "zone_5"):
        assert f'"{key}"' in FEEDBACK
    start = MANAGER.index("def _current_live_intensity")
    end = MANAGER.index("def _check_live_intensity_feedback", start)
    block = MANAGER[start:end]
    assert 'return "under_zone_1"' in block
    assert 'return "zone_1"' in block
    assert 'return "zone_2"' in block
    assert 'return "zone_3"' in block
    assert 'return "zone_4"' in block
    assert 'return "zone_5"' in block


def test_light_feedback_and_restore_disable_transitions():
    assert 'service_data["transition"] = 0' in MANAGER
    assert '"transition": 0' in MANAGER


def test_periodic_ai_requires_actual_live_values_time_context_and_safe_sport():
    start = MANAGER.index("async def _async_periodic_live_message")
    end = MANAGER.index("def _static_periodic_extra_message", start)
    block = MANAGER[start:end]
    assert "Always state elapsed workout time" in block
    assert "heart rate when available" in block
    assert "actual current speed" in block
    assert "activity_kind is running" in block
    assert "motivational" in block


def test_periodic_plain_tts_has_live_calculated_time_and_motivation():
    assert "def _static_periodic_calculated_message" in MANAGER
    assert "session_duration_minutes" in MANAGER
    assert "speed_kmh" in MANAGER
    assert "heart_rate_reserve_percent" in MANAGER
    assert "Κράτησε τον έλεγχο και συνέχισε" in MANAGER
    # Plain-TTS live labels are no longer English-only outside en/el/de.
    for code in ("fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"):
        assert f'"{code}":' in FEEDBACK


def test_hrr_feedback_is_30_second_cadence_and_rpe_after_completion():
    start = MANAGER.index("async def _async_collect_heart_rate_recovery")
    end = MANAGER.index("def session_duration", start)
    block = MANAGER[start:end]
    assert '(10, "hrr_10s", False)' in block
    assert '(30, "hrr_30s", True)' in block
    assert '(60, "hrr_60s", True)' in block
    assert '(90, None, True)' in block
    assert '(120, "hrr_120s", False)' in block
    assert 'if announce_checkpoint:' in block
    assert 'await self._async_announce_session_guidance(\n                    "recovery_complete"' in block
    assert 'await self._async_announce_session_guidance(\n                        "rpe_reminder"' in block

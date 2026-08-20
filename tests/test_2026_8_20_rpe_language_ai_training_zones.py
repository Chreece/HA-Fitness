from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("fitness_workout_prescriptions_standalone", ROOT / "custom_components/fitness/workout_prescriptions.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)
normalize_prescription = _MODULE.normalize_prescription

JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def test_rpe_card_identifies_the_exact_latest_workout_and_when_it_started():
    assert '"start": latest_workout.start if latest_workout is not None else None' in DASHBOARD
    assert '"end": latest_workout.end if latest_workout is not None else None' in DASHBOARD
    assert 'const workoutName = String(latest.name || latest.sport || l.latest_workout)' in JS
    assert 'const workoutWhen = _fitnessDateTimeLabel(latest.start' in JS
    assert 'class="rpe-workout"' in JS


def test_successful_remote_login_persists_selected_portal_language_to_profile_options():
    assert 'def _persist_login_language(self, row: dict[str, Any], language: str) -> None:' in ACCOUNTS
    assert 'options[CONF_LANGUAGE] = normalized' in ACCOUNTS
    assert 'self.hass.config_entries.async_update_entry(entry, options=options)' in ACCOUNTS
    assert 'self._persist_login_language(row, language)' in ACCOUNTS


def test_ai_today_and_weekly_plan_have_in_card_regenerate_controls():
    assert 'vol.Required("type"): "fitness/training/daily_plan"' in DASHBOARD
    assert 'await manager.async_generate_daily_training_plan(force=True)' in DASHBOARD
    assert 'class="regenerate-ai"' in JS
    assert 'this.shadowRoot.querySelector(".regenerate-ai")?.addEventListener("click",()=>this._regenerateDaily())' in JS
    assert 'class="regen"' in JS
    assert "this.shadowRoot.querySelector('.regen')?.addEventListener('click',()=>this._load(true))" in JS


def test_ai_prompts_require_clear_steps_with_training_zone_and_intensity():
    assert '3-12 ordered steps' in MANAGER
    assert 'Every step target MUST contain intensity' in MANAGER
    assert 'training_zone using zone_1, zone_2, zone_3, zone_4 or zone_5' in MANAGER
    assert 'Warm-up, work intervals, recoveries and cool-down' in MANAGER
    assert 'Every step target must include intensity' in MANAGER
    assert 'Warm-up, work, recovery and cool-down steps must state their own zone/intensity' in MANAGER


def test_prescription_normalization_adds_safe_aerobic_zones_but_not_fake_strength_zones():
    cycling = normalize_prescription({
        "sport": "cycling",
        "intensity": "vigorous",
        "steps": [
            {"name": "Warm up", "instruction": "Ride easy", "duration_seconds": 600},
            {"name": "Threshold intervals", "instruction": "Hold threshold effort", "duration_seconds": 900},
            {"name": "Cool down", "instruction": "Recover easily", "duration_seconds": 600},
        ],
    })
    assert cycling["intensity"] == "vigorous"
    assert cycling["training_zone"] == "zone_4"
    assert [step["target"]["training_zone"] for step in cycling["steps"]] == ["zone_2", "zone_4", "zone_1"]
    assert [step["target"]["intensity"] for step in cycling["steps"]] == ["light", "vigorous", "recovery"]

    strength = normalize_prescription({
        "sport": "strength",
        "intensity": "vigorous",
        "steps": [{"name": "Working sets", "instruction": "Hard controlled sets", "target": {"effort": "hard"}}],
    })
    assert strength["steps"][0]["target"]["intensity"] == "vigorous"
    assert "training_zone" not in strength["steps"][0]["target"]


def test_today_and_weekly_cards_render_zone_intensity_and_explicit_step_instructions():
    assert 'function _fitnessZoneForIntensity(value)' in JS
    assert 'class="workout-zone-summary"' in JS
    assert 'class="step-zone-row"' in JS
    assert 'class="step-instruction"' in JS
    assert 't.step_instruction||"What to do"' in JS
    assert '_fitnessWorkoutPrescriptionMarkup(device,this._profile,this._hass)' in JS
    assert '_fitnessWorkoutPrescriptionMarkup(workout,this._profile,this._hass)' in JS
    assert 'day-prescription-meta' in JS

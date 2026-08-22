from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
WORKOUTS = (ROOT / "custom_components/fitness/providers/workouts.py").read_text(encoding="utf-8")
IDENTITY = (ROOT / "custom_components/fitness/live/device_identity.py").read_text(encoding="utf-8")


def test_v140_frontend_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_admin_overview_cast_has_user_style_choices_progress_and_remote_exit_guard():
    block = JS[JS.index("async _openOverviewCastPicker()") : JS.index("async _castOverviewToTarget", JS.index("async _openOverviewCastPicker()"))]
    assert 'id="overview-cast-local"' in block
    assert 'id="overview-cast-target"' in block
    assert 'overview-smart-tv-create' in block
    assert 'overview-cast-local-status' in block
    assert 'overview-cast-ha-status' in block
    assert '_prepareOverviewLocalCastContext' in block
    assert '_ensureOverviewCastBackGuard()' in JS
    assert '_overviewCastExitUntil > now' in JS
    assert '_quitOverviewCastReceiver()' in JS
    assert 'overview-cast-remote-focus' in JS


def test_overview_has_dedicated_about_and_changelog_markup_is_structured():
    assert 'id="about-fitness"' in JS
    assert 'fitness-about-version' in JS
    assert 'fitness-about-changelog' in JS
    assert '_aboutChangelogMarkup(raw)' in JS
    assert 'const heading = line.match' in JS
    assert 'const bullet = line.match' in JS
    assert '_aboutMarkup(step)' not in JS


def test_config_flow_keeps_errors_on_step_and_footer_in_lower_right():
    assert '_missingRequiredFields(step, data)' in JS
    assert 'for (const field of missing) errors[field] = "required";' in JS
    assert 'this._flow = {...currentStep, errors};' in JS
    assert 'position:sticky;bottom:-15px' in JS
    assert '.flow-actions{display:flex;justify-content:flex-end' in JS
    assert 'translatedSaveError' in JS
    assert 'error_save_fitness_settings || "' not in JS


def test_workout_browser_header_tags_and_historical_route_recovery():
    # Name is first metadata chip; there is no separate subtitle under Workouts.
    assert 'workoutName?`<span class="workout-name-tag"><ha-icon icon="mdi:dumbbell"' in JS
    assert 'justify-content:center' in JS[JS.index('class FitnessWorkoutCard'):JS.index('class FitnessSleepRecoveryCard')]
    for key in ('encoded_polyline', 'summary_polyline'):
        assert key in JS
        assert key in WORKOUTS
    assert 'gps_track: list[list[float]] | None = None' in WORKOUTS
    assert 'result["gps_track"] = _persistent_route(self.gps_track)' in WORKOUTS
    assert 'self.gps_track = _find_route(self.extra, self.provider_values)' in WORKOUTS


def test_generic_ant_profile_or_stale_name_cannot_reidentify_removed_device():
    assert 'persisted/generated sensor title as product evidence' in IDENTITY
    assert 'if current_names:' in IDENTITY
    assert 'elif endpoints:' in IDENTITY
    assert 'return False' in IDENTITY
    assert '"Power Meter"' not in IDENTITY

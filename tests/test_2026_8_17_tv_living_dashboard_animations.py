from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "custom_components" / "fitness"
JS = (BASE / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
TV = (BASE / "tv_dashboard.py").read_text(encoding="utf-8")
DASHBOARD = (BASE / "dashboard.py").read_text(encoding="utf-8")


def test_animation_preference_is_profile_scoped_and_defaults_on():
    assert '"animations_enabled": bool(profile.get("animations_enabled", True))' in TV
    assert 'vol.Optional("animations_enabled"): bool' in TV
    assert 'animations_enabled=msg.get("animations_enabled")' in TV
    assert '"animations_enabled": result["animations_enabled"]' in TV
    assert '"animations_enabled": bool(tv_preferences.get("animations_enabled", True))' in DASHBOARD
    assert 'prefs?.animations_enabled ?? this._profile?.tv_dashboard?.animations_enabled ?? true' in JS
    assert 'id="cfg-animations"' in JS
    assert 'animations_enabled:animations' in JS
    assert 'animations_enabled:Boolean(settings.animations_enabled ?? true)' in JS


def test_idle_dashboard_always_has_an_ambient_tone_and_motion_contract():
    assert 'const fallbackRgb = Array.isArray(colors.light)' in JS
    assert ': Array.isArray(colors.moderate) ? colors.moderate' in JS
    assert ': [3,169,244];' in JS
    assert 'const key = Number.isFinite(fitness)' in JS
    assert ': "light";' in JS
    assert ':host([fitness-animations]) .fitness-ambient-layer i:nth-child(1)' in JS
    assert '@keyframes fitness-card-float' in JS
    assert '@keyframes fitness-card-aura' in JS
    assert '@keyframes fitness-toolbar-alive' in JS
    assert '@keyframes fitness-media-alive' in JS


def test_live_workout_motion_changes_with_zone_without_disabling_reduced_motion():
    for zone in ("very_light", "light", "moderate", "vigorous", "near_maximal"):
        assert f'{zone}:' in JS
    assert 'this.style.setProperty("--fitness-motion-speed"' in JS
    assert 'this.style.setProperty("--fitness-motion-lift"' in JS
    assert 'this.style.setProperty("--fitness-energy-alpha"' in JS
    assert 'this.toggleAttribute("fitness-live-ambient", Boolean(tone?.live))' in JS
    assert 'this.setAttribute("fitness-workout-zone"' in JS
    assert ':host([fitness-live-ambient][fitness-animations]) .tv-card-slot' in JS
    assert '@media(prefers-reduced-motion:reduce)' in JS

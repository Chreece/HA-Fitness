from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_card_motion_is_limited_to_semantic_movement_icons():
    assert ':host([fitness-animations]) .tv-card-slot:not(.fitness-remote-section-selected)' not in JS
    assert 'card.__fitnessLivingMode = this._motionEnabled() ? "movement-icons-only" : "static"' in JS
    assert 'const icons = this._cardMotionElements(card, "ha-icon")' in JS
    assert '/heart|pulse|cardio|speedometer|gauge|run|walk|shoe|bike|bicycle|rowing|swim|motion|cadence|rotate/' in JS
    assert 'data-fitness-motion-lite' in JS
    assert 'animation:none!important;transition:none!important' in JS


def test_chart_motion_is_type_specific_and_cannot_create_horizontal_scrollbars():
    assert 'strokeDashoffset:length' in JS
    assert 'transform:"scaleY(0)"' in JS
    assert 'transform:"scaleX(0)"' in JS
    assert 'clipPath:"circle(0% at 50% 50%)"' in JS
    assert 'document.createElementNS("http://www.w3.org/2000/svg", "animateMotion")' in JS
    assert 'svg.style.overflow = "hidden"' in JS
    assert 'overflow-x:clip;overflow-y:visible' in JS
    assert 'animation:fitness-data-sheen' in JS

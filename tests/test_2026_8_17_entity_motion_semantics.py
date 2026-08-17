from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_card_frames_stay_stationary_while_entities_animate_individually():
    assert "Card frames are intentionally stationary" in JS
    assert ':host([fitness-animations]) .tv-card-slot:not(.fitness-remote-section-selected)' not in JS
    assert 'const values = this._cardMotionElements(card' in JS
    assert 'const fills = this._cardMotionElements(card' in JS
    assert 'semantic = "heart"' in JS
    assert 'semantic = "motion"' in JS
    assert 'semantic = "recovery"' in JS
    assert 'semantic = "energy"' in JS
    assert 'semantic = "score"' in JS
    assert 'semantic = "time"' in JS
    assert 'semantic = "status"' in JS


def test_chart_motion_is_type_specific_and_cannot_create_horizontal_scrollbars():
    assert 'strokeDashoffset:length' in JS
    assert 'transform:"scaleY(0)"' in JS
    assert 'transform:"scaleX(0)"' in JS
    assert 'clipPath:"circle(0% at 50% 50%)"' in JS
    assert 'document.createElementNS("http://www.w3.org/2000/svg", "animateMotion")' in JS
    assert 'svg.style.overflow = "hidden"' in JS
    assert 'overflow-x:clip;overflow-y:visible' in JS
    assert 'animation:fitness-data-sheen' in JS

from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()

def test_desktop_masonry_slots_do_not_create_invisible_pointer_overlays():
    assert ".tv-card-slot{min-width:0;position:relative;overflow:visible;min-height:var(--tv-card-visual-height,1px);border-radius:14px;pointer-events:none}" in JS
    assert ".tv-card-slot>.tv-mounted-card{display:block;width:100%;max-width:none;pointer-events:auto}" in JS
    assert ".layout-tools,.card-resize-handle{pointer-events:auto}" in JS

def test_desktop_dashboard_avoids_3d_hit_testing_but_cast_keeps_it():
    assert ".tv-oled-stage{min-width:0;position:relative;z-index:1;perspective:none;transform-style:flat}" in JS
    assert ":host([fitness-cast-receiver]) .tv-oled-stage{perspective:1200px;transform-style:preserve-3d}" in JS

def test_v124_frontend_revision():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS

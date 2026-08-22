from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"custom_components/fitness/frontend/fitness-dashboard.js").read_text()
CF=(ROOT/"custom_components/fitness/config_flow.py").read_text()

def test_remote_users_do_not_get_home_assistant_media_source():
    assert 'this._access?.local_ha_hardware_allowed ? `<button class="music-source" data-source="ha"' in JS
    assert 'if (!this._access?.local_ha_hardware_allowed) { this._renderMusicSources(); return; }' in JS

def test_media_and_profile_proper_nouns_are_not_browser_translated():
    assert 'id="media-title" class="notranslate" translate="no"' in JS
    assert 'class="tv-profile-identity" translate="no"' in JS
    assert 'media-result-copy notranslate" translate="no"' in JS

def test_more_builtin_fitness_themes_are_selectable():
    for theme in ("fitness_neon","fitness_forest","fitness_sunset","fitness_arctic","fitness_high_contrast","fitness_violet"):
        assert theme in CF and theme in JS

def test_average_hr_zone_axis_is_a_smooth_gradient():
    block=JS.split('_heartRateGradient(baseline, span)',1)[1].split('_comparisonRow(metric)',1)[0]
    assert 'pct((zone.lo+zone.hi)/2)' in block
    assert 'linear-gradient(90deg' in block

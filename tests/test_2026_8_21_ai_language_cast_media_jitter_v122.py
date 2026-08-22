from pathlib import Path

ROOT = Path(__file__).resolve().parent
JS = (ROOT.parent / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
MANAGER = (ROOT.parent / "custom_components/fitness/manager.py").read_text()

def test_language_style_is_central_and_greek_is_native_guided():
    assert "def _ai_language_style_guidance" in MANAGER
    assert "natural contemporary Greek coaching language" in MANAGER
    assert "Do not translate JSON keys, enum values, machine tokens" in MANAGER
    assert 'prompt = str(prompt or "").rstrip() + "\\n\\n" + self._ai_language_style_guidance()' in MANAGER

def test_cast_media_commands_are_serialized_and_stale_play_is_cancelled():
    assert "this._mediaCommandGeneration = 0" in JS
    assert "this._mediaCommandQueue = Promise.resolve()" in JS
    assert "return this._handleMediaCommand(command, data);" in JS
    assert "if ([\"pause\",\"stop\"].includes(command))" in JS
    assert "const stillCurrent = () => commandGeneration === Number(this._mediaCommandGeneration || 0) && this._audioOwner" in JS
    assert "if (playbackAllowed && !playbackAllowed()) return false" in JS

def test_cast_quit_has_receiver_and_webview_fallbacks_without_history_authority():
    pop = JS.split("  _handleCastPopstate(event)",1)[1].split("  async _quitCastFromRemote(",1)[0]
    assert "_quitCastFromRemote" not in pop
    assert "await Promise.race([stopped" in JS
    assert 'globalThis.location.replace("about:blank")' in JS

def test_desktop_bottom_layout_does_not_force_scrolltop():
    layout = JS.split("_applyDashboardCardLayout()",1)[1].split("_scheduleDashboardCardLayout()",1)[0]
    assert 'scrollbarGutter = "stable"' in layout
    assert "bottomSurface.scrollTop = target" not in layout
    assert "const settleTolerance = aiSettlingCard ? 6 : 2" in JS
    assert "}, 120);" in JS
    assert "if (wrapper.__fitnessAiResizeTimer) continue;" in JS

def test_v122_cache_contract():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS

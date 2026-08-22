from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_dashcast_load_url_is_the_only_receiver_launch_operation():
    block = DASH[DASH.index("def _launch_dashcast_sync"):DASH.index("async def _async_launch_dashcast")]
    assert "controller.load_url(url, force=True)" in block
    assert "controller.launch(" not in block
    assert "status_text == DASHCAST_READY_STATUS" not in block
    assert "load_done.wait(" not in block


def test_browser_web_sender_cast_is_not_removed_when_dashcast_is_available():
    assert "const localCastVisible = true;" in JS
    assert "context.requestSession()" in JS
    assert "cast_sender.js?loadCastFramework=1" in JS
    assert 'false && localCastCanConfigure ? `<details class="local-cast-config"' in JS

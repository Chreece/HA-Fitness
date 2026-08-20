from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_custom_cards_registry_is_never_replaced():
    public = JS[JS.index("window.customCards = window.customCards || []"):JS.index("console.info(")]
    assert "window.customCards = window.customCards.filter" not in public
    assert "window.customCards.splice(index, 1)" in public
    assert "window.customCards.push(card)" in public


def test_five_public_cards_are_registered_including_wellness():
    public = JS[JS.index("const FITNESS_PUBLIC_CARDS"):JS.index("const publicTypes")]
    assert public.count('type: "fitness-') == 5
    assert 'type: "fitness-live-workout-card"' in public
    for card in (
        "fitness-workout-card",
        "fitness-sleep-recovery-card",
        "fitness-evaluation-card",
        "fitness-wellness-card",
    ):
        assert f'type: "{card}"' in public


def test_public_cards_do_not_auto_preview():
    public = JS[JS.index("const FITNESS_PUBLIC_CARDS"):JS.index("const publicTypes")]
    assert "preview: true" not in public
    assert public.count("preview: false") == 5


def test_public_cards_still_have_visual_editor_support():
    assert "static getConfigElement() { return document.createElement(\"fitness-profile-card-editor\"); }" in JS
    assert 'customElements.define("fitness-profile-card-editor"' in JS


def test_frontend_resource_revision_matches():
    frontend = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    backend = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert frontend and backend
    assert frontend.group(1) == backend.group(1)

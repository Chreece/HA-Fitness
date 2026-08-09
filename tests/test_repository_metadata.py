import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hacs_structure_and_metadata():
    manifest = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())

    assert manifest["domain"] == "fitness"
    assert manifest["name"] == "Fitness"
    assert manifest["version"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].startswith("https://github.com/")
    assert manifest["codeowners"] == ["@Chreece"]
    assert manifest["config_flow"] is True
    assert hacs["name"] == "Fitness"

    custom_components = [
        p for p in (ROOT / "custom_components").iterdir() if p.is_dir()
    ]
    assert [p.name for p in custom_components] == ["fitness"]


def test_brand_and_translations_exist():
    assert (ROOT / "brand/icon.png").is_file()
    assert (ROOT / "custom_components/fitness/brand/icon.png").is_file()
    assert (ROOT / "custom_components/fitness/strings.json").is_file()
    assert len(list((ROOT / "custom_components/fitness/translations").glob("*.json"))) >= 2


def test_all_json_files_parse():
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))



def test_dependabot_automerge_is_bot_only():
    workflow = (
        ROOT / ".github/workflows/dependabot-automerge.yml"
    ).read_text(encoding="utf-8")

    assert "dependabot[bot]" in workflow
    assert "github.event.pull_request.user.login" in workflow
    assert "github.event.pull_request.draft == false" in workflow
    assert "pull-requests: write" in workflow
    assert "contents: write" in workflow
    assert "gh pr merge --auto --squash" in workflow
    assert "--admin" not in workflow



def test_adapter_diagnostics_are_exposed():
    manager = (
        ROOT / "custom_components/fitness/manager.py"
    ).read_text(encoding="utf-8")
    assert "def workout_adapter_diagnostics" in manager
    assert '"workout_adapters": self.workout_adapter_diagnostics()' in manager



def test_session_guidance_is_localized_for_supported_languages():
    feedback = (
        ROOT / "custom_components/fitness/feedback.py"
    ).read_text(encoding="utf-8")
    for language in (
        "en", "el", "de", "fr", "es", "it", "pt", "nl",
        "pl", "ru", "uk", "tr", "zh", "ja", "ko",
    ):
        assert f'"{language}": {{' in feedback
    assert "def static_session_message" in feedback



def test_every_translation_exposes_profile_language():
    translation_dir = ROOT / "custom_components/fitness/translations"
    files = [ROOT / "custom_components/fitness/strings.json", *translation_dir.glob("*.json")]
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["config"]["step"]["user"]["data"]["language"]
        assert data["options"]["step"]["profile"]["data"]["language"]



def test_intensity_light_feedback_is_not_heartbeat_blinking():
    manager = (
        ROOT / "custom_components/fitness/manager.py"
    ).read_text(encoding="utf-8")
    start = manager.index("async def _async_live_intensity_feedback")
    end = manager.index("async def _async_intensity_message", start)
    block = manager[start:end]
    assert "await asyncio.sleep(3.0)" in block
    assert "for pulse_number" not in block

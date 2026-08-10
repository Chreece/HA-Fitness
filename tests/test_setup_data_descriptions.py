import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_shipped_translation_has_setup_data_descriptions():
    files = [
        ROOT / "custom_components/fitness/strings.json",
        *(ROOT / "custom_components/fitness/translations").glob("*.json"),
    ]
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for root_name in ("config", "options"):
            steps = data[root_name]["step"]
            for step_name in (
                "live_devices", "workout_devices", "ai", "feedback"
            ):
                if step_name not in steps:
                    continue
                fields = steps[step_name].get("data", {})
                descriptions = steps[step_name].get("data_description", {})
                for key in fields:
                    assert key in descriptions, (path.name, root_name, step_name, key)


def test_required_and_optional_profile_inputs_are_explained():
    strings = json.loads(
        (ROOT / "custom_components/fitness/strings.json").read_text(
            encoding="utf-8"
        )
    )
    for step_name in ("required", "optional"):
        step = strings["config"]["step"][step_name]
        for key in step["data"]:
            assert key in step["data_description"]

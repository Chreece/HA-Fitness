import re
"""AI-provider default/fallback and pre-release repository contracts."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/fitness"
CONFIG_FLOW = (BASE / "config_flow.py").read_text(encoding="utf-8")
CONST = (BASE / "const.py").read_text(encoding="utf-8")
MANAGER = (BASE / "manager.py").read_text(encoding="utf-8")
SENSOR = (BASE / "sensor.py").read_text(encoding="utf-8")
FRONTEND = (BASE / "frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (BASE / "dashboard.py").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
CONTRIBUTING = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
RELEASE_CHECKLIST = (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
BUG_REPORT = (ROOT / ".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")


def _translation_files():
    return [BASE / "strings.json", *sorted((BASE / "translations").glob("*.json"))]


def test_setup_defaults_to_home_assistant_current_ai_task():
    assert 'AI_ENTITY_SYSTEM_DEFAULT = "__home_assistant_default__"' in CONST
    assert "DATA_PREFERENCES as AI_TASK_DATA_PREFERENCES" in CONFIG_FLOW
    assert 'getattr(preferences, "gen_data_entity_id", None)' in CONFIG_FLOW
    assert "CONF_AI_ENTITY, AI_ENTITY_SYSTEM_DEFAULT" in CONFIG_FLOW
    assert "_optional_suggested(" in CONFIG_FLOW
    assert '"value": AI_ENTITY_SYSTEM_DEFAULT' in CONFIG_FLOW
    assert "_first_ai_task_entity" not in CONFIG_FLOW


def test_default_ai_provider_is_resolved_by_home_assistant_at_every_call():
    assert "entity == AI_ENTITY_SYSTEM_DEFAULT" in MANAGER
    start = MANAGER.index("async def _call_ai_task_service")
    end = MANAGER.index("async def _call_conversation_service", start)
    service = MANAGER[start:end]
    assert 'service_data = {' in service
    assert 'if entity_id:' in service
    assert 'service_data["entity_id"] = entity_id' in service

    start = MANAGER.index("async def _call_ai_unlocked")
    end = MANAGER.index("def _ai_result_language_mismatch", start)
    routing = MANAGER[start:end]
    assert "if configured_entity is None:" in routing
    assert "return await self._call_ai_task_service(prompt, task_name)" in routing


def test_pinned_provider_is_honored_and_unavailability_falls_back_with_repair():
    assert 'if configured_entity.startswith("conversation."):' in MANAGER
    assert 'elif configured_entity.startswith("ai_task."):' in MANAGER
    assert "_call_conversation_service(" in MANAGER
    assert "_call_ai_task_service(" in MANAGER
    assert "async_track_state_change_event(" in MANAGER
    assert "self._async_ai_provider_state_change" in MANAGER
    assert "def _sync_ai_provider_issue" in MANAGER
    assert "ir.async_create_issue(" in MANAGER
    assert 'translation_key="ai_provider_unavailable"' in MANAGER
    assert "ir.async_delete_issue(" in MANAGER
    assert "if not self._ai_provider_available(configured_entity):" in MANAGER


def test_default_sentinel_is_not_exposed_as_ai_entity_attribute():
    assert 'self.manager.config.get("ai_entity") or "preferred_default"' in SENSOR


def test_ai_provider_guidance_and_repair_are_localized_everywhere():
    for path in _translation_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("config", "options"):
            ai = data[section]["step"]["ai"]
            assert ai["description"]
            assert ai["data"]["ai_entity"]
            assert ai["data_description"]["ai_entity"]
        issue = data["issues"]["ai_provider_unavailable"]
        assert issue["title"]
        assert "{entity_id}" in issue["description"]


def test_repository_remains_unreleased_until_first_public_release():
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.0.0" or re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:(?:a\d+)|-(?:alpha|beta)\d+)?", manifest["version"])
    assert "## Unreleased" in CHANGELOG
    assert "has **not had a public release yet**" in CHANGELOG
    assert "`YYYY.MM.RR-betaXX`" in CHANGELOG
    assert "`YYYY.MM.RR`" in CHANGELOG
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in DASHBOARD
    assert "2026.08.01-beta01" in CONTRIBUTING
    assert "2026.08.01" in CONTRIBUTING
    assert "YYYY.MM.RR-betaXX" in RELEASE_CHECKLIST
    assert "Unreleased (commit SHA) or 2026.08.01-beta01" in BUG_REPORT

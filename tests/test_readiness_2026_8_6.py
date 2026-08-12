from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
ENTITY = (ROOT / "custom_components/fitness/entity.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_readiness_is_fitness_owned_and_transparent():
    assert "def readiness_evaluation" in MANAGER
    assert '"data_source": "fitness_canonical_recovery_data"' in MANAGER
    assert '"components": components' in MANAGER
    assert "effective_weight_percent" in MANAGER
    assert "weights are renormalized" in MANAGER


def test_readiness_entity_is_on_recovery_device():
    assert 'Desc(key="readiness"' in SENSOR
    assert 'kind="sleep", metric="readiness"' in SENSOR
    assert 'translated_kind = "recovery" if kind == "sleep" else kind' in ENTITY
    assert 'translation_key=translated_kind' in ENTITY


def test_readiness_attributes_expose_evidence():
    start = SENSOR.index('if m == "readiness":', SENSOR.index("def extra_state_attributes"))
    end = SENSOR.index("sleep = self.manager.latest_sleep()", start)
    section = SENSOR[start:end]

    # Readiness exposes its calculated evidence directly through the normal
    # evaluation-details path; it must never call the removed helper that caused
    # the Home Assistant AttributeError.
    assert "self._readiness_data_used" not in section
    assert "evaluation_user_details(" in section
    assert '"score": readiness.get("score")' in section
    assert '"level": readiness.get("level")' in section
    assert '"confidence_percent": readiness.get("confidence_percent")' in section
    assert '"available_components": readiness.get("available_components")' in section
    assert '"components": readiness.get("components")' in section
    assert '"data_source": readiness.get("data_source")' in section

def test_all_supported_translations_have_recovery_and_readiness():
    translations = ROOT / "custom_components/fitness/translations"
    expected = {"en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko"}
    assert {p.stem for p in translations.glob("*.json")} >= expected
    for code in expected:
        data = json.loads((translations / f"{code}.json").read_text(encoding="utf-8"))
        assert data["device"]["recovery"]["name"]
        assert data["entity"]["sensor"]["readiness"]["name"]


def test_recovery_card_uses_readiness_with_colored_levels():
    section = FRONTEND[FRONTEND.index("class FitnessRecoveryCard"):FRONTEND.index("class FitnessTrainingLoadCard")]
    assert "e.readiness" in section
    assert "FITNESS_READINESS_LEVELS" in FRONTEND
    for tone in ("tone-excellent","tone-high","tone-moderate","tone-low","tone-very-low"):
        assert tone in section
    assert "components" in section

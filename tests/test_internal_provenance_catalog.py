from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPL = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")


def test_internal_provenance_catalog_is_ai_free():
    start = EXPL.index("_PROVENANCE_TEXT =")
    end = EXPL.index("def provenance_text", start)
    block = EXPL[start:end].lower()

    for forbidden in (
        "_call_ai",
        "conversation.process",
        "ai_task.generate_data",
        "services.async_call",
    ):
        assert forbidden not in block

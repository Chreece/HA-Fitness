from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = ROOT / "custom_components/fitness/manager.py"
MANAGER = MANAGER_PATH.read_text(encoding="utf-8")


def test_all_referenced_conf_constants_are_imported_from_const():
    tree = ast.parse(MANAGER)
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "const":
            imported.update(alias.name for alias in node.names)
    referenced = set(re.findall(r"\bCONF_[A-Z0-9_]+\b", MANAGER))
    assert referenced <= imported, sorted(referenced - imported)


def test_birth_provenance_constants_are_imported():
    for name in ("CONF_BIRTH_DAY", "CONF_BIRTH_MONTH", "CONF_BIRTH_YEAR"):
        assert f"    {name}," in MANAGER


def test_notify_isolates_listener_exceptions():
    start = MANAGER.index("def _notify(self):")
    end = MANAGER.index("async def _save", start)
    block = MANAGER[start:end]
    assert "try:" in block
    assert "except Exception:" in block
    assert "_LOGGER.exception" in block

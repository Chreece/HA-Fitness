from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = ROOT / "custom_components/fitness/manager.py"
MANAGER = MANAGER_PATH.read_text(encoding="utf-8")


def _top_level_imported_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
            )
    return names


def test_provenance_text_is_imported_before_use():
    tree = ast.parse(MANAGER)
    imported = _top_level_imported_names(tree)
    assert "provenance_text" in imported
    assert "provenance_text(language, kind)" in MANAGER


def test_birth_constants_are_imported_before_use():
    tree = ast.parse(MANAGER)
    imported = _top_level_imported_names(tree)
    for name in (
        "CONF_BIRTH_DAY",
        "CONF_BIRTH_MONTH",
        "CONF_BIRTH_YEAR",
    ):
        assert name in imported

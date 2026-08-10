from pathlib import Path
import ast
import builtins

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _module_globals():
    names = set(dir(builtins))
    for node in TREE.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _find_method(name):
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(name)


def _direct_scope_unresolved(method):
    """Check only this method's own scope; do not descend into nested functions."""
    globals_ = _module_globals()
    locals_ = {"self"}
    locals_.update(arg.arg for arg in method.args.args)
    locals_.update(arg.arg for arg in method.args.kwonlyargs)

    class Collector(ast.NodeVisitor):
        def __init__(self):
            self.loads = set()
            self.stores = set()

        def visit_FunctionDef(self, node):
            if node is method:
                for stmt in node.body:
                    self.visit(stmt)
            else:
                self.stores.add(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            return

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):
                self.loads.add(node.id)
            elif isinstance(node.ctx, ast.Store):
                self.stores.add(node.id)

    collector = Collector()
    collector.visit(method)
    locals_.update(collector.stores)
    return {
        name
        for name in collector.loads
        if name not in locals_ and name not in globals_
    }


def test_localized_evaluation_provenance_has_no_unresolved_names():
    method = _find_method("localized_evaluation_provenance")
    assert _direct_scope_unresolved(method) == set()

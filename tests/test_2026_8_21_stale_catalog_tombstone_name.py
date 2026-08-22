from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "custom_components" / "fitness" / "live" / "runtime.py"


def _method(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"method {name} not found")


def test_tombstoned_catalog_title_can_be_rebased_from_meaningful_current_name_without_vendor():
    repair = _method(RUNTIME, "_rebase_tombstoned_single_route_identity")
    assert "candidate_is_meaningful" in repair
    assert "stale_product = catalog_product_id(sensor.name, sensor.endpoints)" in repair
    assert "catalog_product_id(candidate_name, {transport: endpoint})" in repair
    assert "observed_product != stale_product" in repair
    assert "and not catalog_name_conflict" in repair
    assert 'sensor.metadata.pop("discovery_confirmed", None)' in repair
    assert 'sensor.metadata["identity_reclassified"]' in repair
    assert "catalog:" in repair


def test_tombstone_repair_still_preserves_existing_vendor_conflict_guard_and_reassignment():
    repair = _method(RUNTIME, "_rebase_tombstoned_single_route_identity")
    assert "sensor.sensor_id not in self._requires_reassignment" in repair
    assert "incoming_vendor == stale_name_vendor" in repair
    assert "_requires_reassignment.discard" not in repair
    assert "sensor.capabilities.clear()" in repair
    assert "endpoint.capabilities.clear()" in repair

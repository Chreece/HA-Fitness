from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT / "custom_components/fitness/providers/workout_adapters/registry.py"
).read_text(encoding="utf-8")
WORKOUTS = (
    ROOT / "custom_components/fitness/providers/workouts.py"
).read_text(encoding="utf-8")


def test_explicit_precedes_scoped_fallback():
    explicit = REGISTRY.index("adapter.discover(hass, config)")
    success = REGISTRY.index("if explicit:", explicit)
    fallback = REGISTRY.index("fallback = _mark_fallback(", success)
    assert explicit < success < fallback
    assert "only_domains=set(adapter.domains)" in REGISTRY
    assert "only_device_ids=device_ids" in REGISTRY


def test_successful_explicit_adapter_skips_fallback():
    success = REGISTRY.index("if explicit:")
    continue_pos = REGISTRY.index("continue", success)
    fallback = REGISTRY.index("fallback = _mark_fallback(", success)
    assert continue_pos < fallback


def test_unknown_integrations_stay_generic_and_scoped():
    assert "unknown_device_ids" in REGISTRY
    assert "if unknown_device_ids:" in REGISTRY
    assert "exclude_domains=set(EXPLICIT_DOMAINS)" in REGISTRY
    assert "only_device_ids=unknown_device_ids" in REGISTRY
    assert "unknown_device_ids or None" not in REGISTRY


def test_generic_parser_supports_scoping():
    assert "only_domains: set[str] | None = None" in WORKOUTS
    assert "only_device_ids: set[str] | None = None" in WORKOUTS
    assert "provider not in only_domains" in WORKOUTS
    assert "entry.device_id not in only_device_ids" in WORKOUTS


def test_adapter_errors_are_isolated():
    assert "except Exception as err:" in REGISTRY
    assert 'diag.error = f"{type(err).__name__}: {err}"' in REGISTRY
    assert 'diag.status = "no_usable_workout"' in REGISTRY

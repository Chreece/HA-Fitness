from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"


def load_module(name: str, relative_path: str):
    spec = spec_from_file_location(name, FITNESS / relative_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_homeassistant_stubs():
    """Minimal stubs needed to import provider helper modules for unit tests."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")

    class HomeAssistant:
        pass

    def valid_entity_id(value: str) -> bool:
        if not isinstance(value, str) or "." not in value:
            return False
        domain, object_id = value.split(".", 1)
        return bool(domain and object_id and " " not in value)

    core.HomeAssistant = HomeAssistant
    core.valid_entity_id = valid_entity_id
    entity_registry.async_get = lambda hass: None

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry

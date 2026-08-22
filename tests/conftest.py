from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "custom_components" / "fitness"

# Load pure Fitness helper modules in unit tests without executing the Home
# Assistant integration package __init__.py.  CI installs only the deliberately
# small test requirements, so namespace packages keep calculation/catalog tests
# independent of a full Home Assistant runtime.
if "custom_components" not in sys.modules:
    custom_components_pkg = types.ModuleType("custom_components")
    custom_components_pkg.__path__ = [str(ROOT / "custom_components")]
    sys.modules["custom_components"] = custom_components_pkg
if "custom_components.fitness" not in sys.modules:
    fitness_pkg = types.ModuleType("custom_components.fitness")
    fitness_pkg.__path__ = [str(FITNESS)]
    sys.modules["custom_components.fitness"] = fitness_pkg


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

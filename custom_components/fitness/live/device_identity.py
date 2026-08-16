"""Canonical identity resolution for merged ANT+/Bluetooth fitness sensors."""
from __future__ import annotations
import json
from pathlib import Path
import re
from typing import Any

CATALOG_PATH = Path(__file__).with_name("device_catalog.json")

_FIELD_ALIASES = {
    "manufacturer_name": "manufacturer", "manufacturer": "manufacturer",
    "model_name": "model", "model": "model", "model_number_string": "model",
    "model_no": "model_id",
    "serial": "serial_number", "serial_no": "serial_number",
    "device_serial": "serial_number", "serial_number": "serial_number",
    "hardware_revision": "hw_version", "hardware_rev": "hw_version", "hw_version": "hw_version",
    "software_revision": "sw_version", "software_ver": "sw_version", "sw_version": "sw_version",
    "firmware_revision": "firmware_version", "firmware_version": "firmware_version",
    "model_id": "model_id",
}

def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip("\x00 ")
    return value or None

def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

def _numeric_only(value: Any) -> bool:
    text = _text(value)
    return bool(text and re.fullmatch(r"[0-9._-]+", text))

def _looks_address(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", text))

_EMPTY_CATALOG: dict[str, Any] = {
    "version": 1,
    "manufacturers": {},
    "products": [],
    "profile_models": {},
    "antplus_model_catalog": {},
    "model_catalog": {},
}

def _load_catalog_at_import() -> dict[str, Any]:
    """Load the optional recognition catalog outside radio callbacks.

    A missing, truncated, or malformed catalog must never prevent Fitness from
    starting. Identity recognition degrades to protocol/GATT facts instead.
    """
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return dict(_EMPTY_CATALOG)
    return raw if isinstance(raw, dict) else dict(_EMPTY_CATALOG)

_CATALOG = _load_catalog_at_import()

def load_catalog() -> dict[str, Any]:
    """Return the immutable process-local catalog snapshot."""
    return _CATALOG

def canonical_identity_fields(metadata: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in metadata.items():
        target = _FIELD_ALIASES.get(str(key))
        if target is None:
            continue
        text = _text(value)
        if text is None:
            continue
        if target == "model" and _numeric_only(text):
            result.setdefault("model_id", text)
            continue
        result[target] = text
    return result

def _catalog_manufacturer(endpoints: dict[str, Any]) -> str | None:
    catalog = load_catalog().get("manufacturers", {})
    ant_map = catalog.get("antplus", {}) or {}
    bt_map = catalog.get("bluetooth_manufacturer_data", {}) or {}
    ant = endpoints.get("antplus")
    if ant is not None:
        mid = ant.metadata.get("manufacturer_id")
        if mid is not None and str(mid) in ant_map:
            return str(ant_map[str(mid)])
    bt = endpoints.get("bluetooth")
    if bt is not None:
        for value in bt.metadata.get("manufacturer_data_ids") or []:
            if str(value) in bt_map:
                return str(bt_map[str(value)])
    return None

def _matches_rule(rule: dict[str, Any], name: str, endpoints: dict[str, Any]) -> bool:
    prefix = _text(rule.get("name_prefix"))
    if prefix and _clean(name).startswith(_clean(prefix)):
        return True
    transport = rule.get("transport")
    if not transport:
        return False
    endpoint = endpoints.get(str(transport))
    if endpoint is None:
        return False
    if "manufacturer_id" in rule and endpoint.metadata.get("manufacturer_id") != rule.get("manufacturer_id"):
        return False
    if "manufacturer_data_id" in rule and rule.get("manufacturer_data_id") not in (endpoint.metadata.get("manufacturer_data_ids") or []):
        return False
    if "model_no" in rule and endpoint.metadata.get("model_no") != rule.get("model_no"):
        return False
    return True


def catalog_transport_correlation(sensor) -> dict[str, Any] | None:
    """Return a data-driven cross-transport correlation role for one sensor.

    Correlation rules are intentionally kept in ``device_catalog.json`` so the
    runtime remains vendor/product agnostic. They are only a fallback when a
    protocol does not expose a common strong serial/product identity.
    """
    if len(getattr(sensor, "endpoints", {}) or {}) != 1:
        return None
    transport, endpoint = next(iter(sensor.endpoints.items()))
    capabilities = set(getattr(sensor, "capabilities", set()) or set())
    advertised = _text(endpoint.metadata.get("advertised_name")) or _text(getattr(sensor, "name", None)) or ""

    for rule in load_catalog().get("transport_correlation_rules", []) or []:
        if not isinstance(rule, dict):
            continue
        expected_caps = {str(value) for value in (rule.get("capabilities") or [])}
        # A correlation rule describes the minimum semantic surface that must be
        # shared. Extra capabilities (for example passive battery or diagnostics)
        # must not prevent the same physical device from correlating.
        if expected_caps and not expected_caps.issubset(capabilities):
            continue
        roles = rule.get("roles") or {}
        role = roles.get(str(transport))
        if not isinstance(role, dict):
            continue

        prefixes = [str(value) for value in (role.get("name_prefixes") or []) if str(value).strip()]
        if prefixes and not any(_clean(advertised).startswith(_clean(prefix)) for prefix in prefixes):
            continue
        if "manufacturer_id" in role and endpoint.metadata.get("manufacturer_id") != role.get("manufacturer_id"):
            continue
        if "manufacturer_data_id" in role:
            manufacturer_data_ids = {
                int(value) for value in (endpoint.metadata.get("manufacturer_data_ids") or [])
                if str(value).strip()
            }
            try:
                required_manufacturer_data_id = int(role.get("manufacturer_data_id"))
            except (TypeError, ValueError):
                continue
            if required_manufacturer_data_id not in manufacturer_data_ids:
                continue
        required_profiles = {int(value) for value in (role.get("profiles") or [])}
        endpoint_profiles = {int(value) for value in (endpoint.metadata.get("profiles") or [])}
        if required_profiles and not required_profiles.issubset(endpoint_profiles):
            continue
        any_profiles = {int(value) for value in (role.get("profiles_any") or [])}
        if any_profiles and not (any_profiles & endpoint_profiles):
            continue
        if role.get("require_serial"):
            identity = canonical_identity_fields(endpoint.metadata)
            if not identity.get("serial_number"):
                continue

        try:
            max_age = float(rule.get("max_age_seconds", 300.0))
        except (TypeError, ValueError):
            max_age = 300.0
        return {
            "rule_id": str(rule.get("id") or "catalog_correlation"),
            "role": str(transport),
            "max_age_seconds": max(1.0, max_age),
        }
    return None


def catalog_product_id(name: str, endpoints: dict[str, Any]) -> str | None:
    """Return the data-driven product-family ID for safe cross-transport merge."""
    for product in load_catalog().get("products", []) or []:
        if not isinstance(product, dict):
            continue
        rules = product.get("match_any") or []
        if any(isinstance(rule, dict) and _matches_rule(rule, name, endpoints) for rule in rules):
            value = _text(product.get("id"))
            if value:
                return value
    return None

def _catalog_product(name: str, endpoints: dict[str, Any]) -> dict[str, str]:
    for product in load_catalog().get("products", []) or []:
        if not isinstance(product, dict):
            continue
        rules = product.get("match_any") or []
        if any(isinstance(rule, dict) and _matches_rule(rule, name, endpoints) for rule in rules):
            return {key: str(product[key]) for key in ("name", "manufacturer", "model", "model_id") if product.get(key) not in (None, "")}
    return {}

def _generic_profile_model(endpoints: dict[str, Any]) -> str | None:
    ant = endpoints.get("antplus")
    if ant is None:
        return None
    profiles = [int(x) for x in (ant.metadata.get("profiles") or []) if str(x).isdigit()]
    models = load_catalog().get("profile_models", {}) or {}
    names = [str(models[str(profile)]) for profile in profiles if str(profile) in models]
    return names[0] if names else None


def _catalog_model(sensor) -> dict[str, str]:
    """Resolve a product generation from a manufacturer-scoped model catalog.

    Catalog entries explicitly declare which protocol field contains the product
    generation model ID. This is intentionally different from treating every ANT
    Common Page ``model_no`` or Bluetooth PnP product ID as the consumer model
    number: those identifiers are manufacturer/protocol-specific and can use a
    completely different numbering scheme.
    """
    endpoints = getattr(sensor, "endpoints", {}) or {}
    catalog = load_catalog().get("model_catalog", {}) or {}

    for vendor in catalog.values():
        if not isinstance(vendor, dict):
            continue
        match = vendor.get("manufacturer_match") or {}
        matched = False

        ant = endpoints.get("antplus")
        ant_ids = {_parse_int(value) for value in (match.get("antplus_manufacturer_ids") or [])}
        ant_ids.discard(None)
        if ant is not None and _parse_int(ant.metadata.get("manufacturer_id")) in ant_ids:
            matched = True

        bt = endpoints.get("bluetooth")
        bt_company_ids = {_parse_int(value) for value in (match.get("bluetooth_manufacturer_data_ids") or [])}
        bt_company_ids.discard(None)
        if bt is not None and bt_company_ids:
            observed = {_parse_int(value) for value in (bt.metadata.get("manufacturer_data_ids") or [])}
            observed.discard(None)
            if observed & bt_company_ids:
                matched = True

        gatt_names = {_clean(value) for value in (match.get("gatt_manufacturer_names") or []) if _text(value)}
        if bt is not None and gatt_names:
            gatt_manufacturer = _clean(bt.metadata.get("manufacturer"))
            if gatt_manufacturer and gatt_manufacturer in gatt_names:
                matched = True

        if not matched:
            continue

        model_id = None
        model_source = None
        for raw_source in vendor.get("model_id_sources") or []:
            if isinstance(raw_source, str):
                source = raw_source
                source_cfg = {}
            elif isinstance(raw_source, dict):
                source = str(raw_source.get("source") or "")
                source_cfg = raw_source
            else:
                continue

            value = None
            if source == "bluetooth_gatt_model_number" and bt is not None:
                # Device Information Model Number may be a purely numeric product
                # generation ID. Non-numeric model strings remain
                # useful identity text but are not fed into numeric range catalogs.
                value = _parse_int(bt.metadata.get("model"))
                if value is None:
                    value = _parse_int(bt.metadata.get("model_number_string"))
            elif source == "antplus_model_no" and ant is not None:
                value = _parse_int(ant.metadata.get("model_no"))
            elif source == "resolved_model_id":
                value = _parse_int(getattr(sensor, "metadata", {}).get("model_id"))

            if value is None:
                continue
            minimum = _parse_int(source_cfg.get("valid_min"))
            maximum = _parse_int(source_cfg.get("valid_max"))
            if minimum is not None and value < minimum:
                continue
            if maximum is not None and value > maximum:
                continue
            model_id = value
            model_source = source
            break

        if model_id is None:
            continue

        for entry in vendor.get("models", []) or []:
            if not isinstance(entry, dict):
                continue
            exact = _parse_int(entry.get("id"))
            minimum = _parse_int(entry.get("min"))
            maximum = _parse_int(entry.get("max"))
            ids = {_parse_int(value) for value in (entry.get("ids") or [])}
            ids.discard(None)
            if exact is not None:
                matches = model_id == exact
            elif ids:
                matches = model_id in ids
            else:
                if minimum is not None and model_id < minimum:
                    continue
                if maximum is not None and model_id > maximum:
                    continue
                matches = minimum is not None or maximum is not None
            if not matches:
                continue

            resolved: dict[str, str] = {
                "model_id": str(model_id),
                "model_id_source": str(model_source or "catalog"),
            }
            manufacturer = _text(entry.get("manufacturer")) or _text(vendor.get("manufacturer"))
            if manufacturer:
                resolved["manufacturer"] = manufacturer
            for key in ("name", "model", "release", "paired_product_name", "paired_product_release"):
                value = _text(entry.get(key))
                if value:
                    resolved[key] = value
            return resolved
    return {}


def _parse_int(value: Any) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(text, 0)
    except (TypeError, ValueError):
        if text.isdigit():
            try:
                return int(text, 10)
            except ValueError:
                return None
    return None


def _extract_cross_transport_value(metadata: dict[str, Any], spec: dict[str, Any]) -> str | None:
    source = str(spec.get("source") or "").strip()
    if not source:
        return None
    value = metadata.get(source)
    if value in (None, ""):
        return None

    pattern = spec.get("regex")
    if pattern:
        match = re.search(str(pattern), str(value), re.IGNORECASE)
        if match is None:
            return None
        group = int(spec.get("group", 1))
        try:
            value = match.group(group)
        except (IndexError, ValueError):
            return None

    transform = str(spec.get("transform") or "text").lower()
    if transform in {"integer", "int"}:
        parsed = _parse_int(value)
        return str(parsed) if parsed is not None else None
    if transform == "lower16":
        parsed = _parse_int(value)
        return str(parsed & 0xFFFF) if parsed is not None else None
    if transform == "lower20":
        parsed = _parse_int(value)
        return str(parsed & 0xFFFFF) if parsed is not None else None
    return _clean(value) or None


def catalog_cross_transport_ids(
    name: str, transport: str, metadata: dict[str, Any], capabilities: set[str] | None = None
) -> set[tuple[str, str, str]]:
    """Return strong cross-transport identifiers exposed by one endpoint.

    The runtime is deliberately vendor-agnostic. Vendor/profile-specific extraction
    lives in ``device_catalog.json``. Returned tuples are ``(rule_id, key, value)``.
    Only exact tuple matches are eligible for automatic physical-device merging.
    """
    result: set[tuple[str, str, str]] = set()
    endpoint_caps = set(capabilities or set())

    # Protocol-native explicit ANT identifiers are always safe to surface. BLE
    # vendor decoders may also populate one of the same semantic metadata keys.
    direct_keys = (
        "ant_device_number", "antplus_device_number", "ant_id", "antplus_id"
    )
    direct_value = None
    for key in direct_keys:
        parsed = _parse_int(metadata.get(key))
        if parsed is not None:
            direct_value = parsed
            break
    if direct_value is None and transport == "antplus":
        direct_value = _parse_int(metadata.get("device_number"))
    if direct_value is not None:
        # ANT device numbers are 16-bit channel identifiers and can collide across
        # unrelated ANT profiles. Scope generic matches by semantic capability so
        # an HR endpoint can never merge with an unrelated speed/power device that
        # happens to reuse the same numeric channel ID.
        for capability in sorted(endpoint_caps):
            result.add((
                "explicit_ant_id",
                f"ant_device_number:{capability}",
                str(direct_value),
            ))

    for rule in load_catalog().get("cross_transport_identity_rules", []) or []:
        if not isinstance(rule, dict):
            continue
        roles = rule.get("roles") or {}
        role = roles.get(str(transport))
        if not isinstance(role, dict):
            continue
        expected_caps = {str(value) for value in (rule.get("capabilities") or [])}
        if expected_caps and not expected_caps.issubset(endpoint_caps):
            continue
        prefixes = [str(value) for value in (role.get("name_prefixes") or []) if str(value).strip()]
        advertised = _text(metadata.get("advertised_name")) or _text(name) or ""
        if prefixes and not any(_clean(advertised).startswith(_clean(prefix)) for prefix in prefixes):
            continue
        if "manufacturer_id" in role and metadata.get("manufacturer_id") != role.get("manufacturer_id"):
            continue
        required_profiles = {int(value) for value in (role.get("profiles") or [])}
        endpoint_profiles = {int(value) for value in (metadata.get("profiles") or [])}
        if required_profiles and not required_profiles.issubset(endpoint_profiles):
            continue

        rule_id = str(rule.get("id") or "catalog_cross_transport_id")
        for spec in role.get("extractors") or []:
            if not isinstance(spec, dict):
                continue
            target = str(spec.get("target") or "").strip()
            if not target:
                continue
            extracted = _extract_cross_transport_value(metadata, spec)
            if extracted is not None:
                result.add((rule_id, target, extracted))
    return result


def resolve_identity(sensor) -> dict[str, Any]:
    candidates: dict[str, tuple[int, str]] = {}
    def offer(field: str, value: Any, score: int) -> None:
        text = _text(value)
        if text is None:
            return
        if field == "model" and _numeric_only(text):
            offer("model_id", text, score)
            return
        previous = candidates.get(field)
        if previous is None or score > previous[0]:
            candidates[field] = (score, text)

    for key, value in canonical_identity_fields(sensor.metadata).items():
        offer(key, value, 60)
    for transport, endpoint in sensor.endpoints.items():
        # Standard GATT Device Information is the most specific product identity
        # source. Catalog rules fill gaps / prettify generic protocol IDs, but do
        # not override an exact model/revision reported by the device itself.
        base = 100 if endpoint.metadata.get("identity_source") == "gatt_device_information" else (65 if transport == "antplus" else 55)
        for key, value in canonical_identity_fields(endpoint.metadata).items():
            offer(key, value, base)

    product = _catalog_product(sensor.name, sensor.endpoints)
    for key, value in product.items():
        offer(key, value, 90)
    # Manufacturer-scoped catalog resolution is authoritative only when the
    # catalog explicitly accepts the protocol field that supplied the model ID.
    # Give that verified generation precedence over generic product-family labels.
    catalog_model = _catalog_model(sensor)
    for key in ("manufacturer", "model", "model_id"):
        if catalog_model.get(key):
            offer(key, catalog_model[key], 110)
    manufacturer = _catalog_manufacturer(sensor.endpoints)
    if manufacturer:
        offer("manufacturer", manufacturer, 75)
    generic_model = _generic_profile_model(sensor.endpoints)
    if generic_model:
        offer("model", generic_model, 35)
    if "firmware_version" in candidates:
        offer("sw_version", candidates["firmware_version"][1], candidates["firmware_version"][0] + 1)

    identity = {key: value for key, (_score, value) in candidates.items()}
    for key in ("release", "paired_product_name", "paired_product_release", "model_id_source"):
        if catalog_model.get(key):
            identity[key] = catalog_model[key]
    name = catalog_model.get("name") or product.get("name")
    if not name:
        advertised = _text(sensor.name)
        if advertised and advertised != "Fitness sensor" and not _looks_address(advertised) and not _numeric_only(advertised):
            if not re.fullmatch(r".+\s+[0-9._-]+", advertised):
                name = advertised
    if not name:
        manufacturer = identity.get("manufacturer")
        model = identity.get("model")
        if manufacturer and model:
            name = model if _clean(manufacturer) in _clean(model) else f"{manufacturer} {model}"
        elif model:
            name = model
        elif manufacturer and generic_model:
            name = f"{manufacturer} {generic_model}"
        elif generic_model:
            name = generic_model
        else:
            name = "Fitness sensor"
    identity["name"] = name
    identity["ready"] = bool(product or identity.get("model") or (identity.get("manufacturer") and identity.get("serial_number")))
    return identity

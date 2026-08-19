"""Config flow for Fitness."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import asyncio
import json

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ai_task.const import (
    DATA_PREFERENCES as AI_TASK_DATA_PREFERENCES,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_TRAINING_GOAL,
    CONF_TRAINING_GOAL_DATE,
    CONF_TRAINING_DAYS_PER_WEEK,
    AI_ENTITY_SYSTEM_DEFAULT,
    CONF_BIRTH_DAY,
    CONF_BIRTH_MONTH,
    CONF_BIRTH_YEAR,
    CONF_FEEDBACK_AREA_IDS,
    CONF_FEEDBACK_LIGHT_IDS,
    CONF_NOTIFY_ENTITY_IDS,
    CONF_TTS_ENTITY_ID,
    CONF_TTS_MEDIA_PLAYER_IDS,
    CONF_TV_DASHBOARD_ENABLED,
    CONF_TV_MEDIA_PLAYER_ID,
    CONF_TV_DUCKING_PERCENT,
    CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    CONF_DASHBOARD_THEME,
    CONF_DASHBOARD_MODULES,
    CONF_DASHBOARD_RSS_ENTITY_IDS,
    CONF_DASHBOARD_MUSIC_ENTITY_IDS,
    CONF_DASHBOARD_LIGHT_ENTITY_IDS,
    CONF_DASHBOARD_VIDEO_ENTITY_IDS,
    CONF_DASHBOARD_WEATHER_ENTITY_ID,
    DASHBOARD_MODULES,
    DEFAULT_DASHBOARD_MODULES,
    DEFAULT_TV_DUCKING_PERCENT,
    DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
    CONF_DATE_OF_BIRTH,
    CONF_DETAILED_STRENGTH_ANALYSIS,
    CONF_HEIGHT,
    CONF_LANGUAGE,
    CONF_LIVE_DEVICE_IDS,
    CONF_LIVE_SENSOR_IDS,
    CONF_MAX_HR,
    CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
    CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
    CONF_PROFILE_NAME,
    CONF_RESTING_HR,
    CONF_SEX,
    CONF_THRESHOLD_HR,
    CONF_THRESHOLD_PACE,
    CONF_THRESHOLD_POWER,
    CONF_VO2MAX,
    CONF_WEIGHT,
    CONF_WEIGHT_SCALE_ENTITY,
    CONF_WORKOUT_DEVICE_IDS,
    CONF_WORKOUT_RETENTION_DAYS,
    CONF_FIT_FILE_RETENTION_COUNT,
    CONF_SLEEP_DEVICE_IDS,
    DEFAULT_WORKOUT_RETENTION_DAYS,
    DEFAULT_FIT_FILE_RETENTION_COUNT,
    MAX_WORKOUT_RETENTION_DAYS,
    DOMAIN,
    SUPPORTED_LANGUAGES,
)
from .providers.entities import (
    is_entity_reference,
    resolve_number_or_entity,
    validate_number_or_entity,
)
from .providers.autofill import exact_profile_defaults
from .providers.capabilities import (
    live_device_choices,
    profile_entity_choices,
    profile_entity_supported,
    sleep_device_choices,
    weight_scale_entity_choices,
    weight_scale_entity_supported,
    workout_device_choices,
)
from .smart_workout_devices import (
    DEVICE_TYPE_AUTO,
    DEVICE_TYPES,
    MAX_SMART_WORKOUT_DEVICE_CHOICES,
    SUPPORTED_SETUP_VENDORS,
    is_smart_workout_candidate,
    setup_vendor,
    smart_workout_archive_compatibility,
    smart_workout_capability_labels,
    smart_workout_device_type,
    smart_workout_model_label,
    smart_workout_vendor,
)


def _text():
    return selector.TextSelector(selector.TextSelectorConfig(multiline=False))


def _normalize_language(value) -> str:
    """Normalize a HA/UI language value to one supported Fitness language."""
    language = str(value or "en").lower()
    code = language.split("-")[0].split("_")[0]
    return code if code in SUPPORTED_LANGUAGES else "en"


def _default_language(hass) -> str:
    """Use Home Assistant's configured UI language as the setup default."""
    return _normalize_language(
        getattr(hass.config, "language", None)
    )


def _language_selector():
    """Select only languages for which Fitness ships localized guidance."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": code, "label": label}
                for code, label in SUPPORTED_LANGUAGES.items()
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )



_PROFILE_ENTITY_QUANTITY = {
    CONF_WEIGHT: "weight",
    CONF_RESTING_HR: "heart_rate",
    CONF_HEIGHT: "height",
    CONF_MAX_HR: "heart_rate",
    CONF_VO2MAX: "vo2max",
    CONF_THRESHOLD_HR: "heart_rate",
    CONF_THRESHOLD_PACE: "pace",
    CONF_THRESHOLD_POWER: "power",
}


def _compatible_profile_entities(
    hass, field: str, profile_entry_id: str | None = None
) -> list[dict[str, str]]:
    """Return only unclaimed entities the runtime profile parser can consume."""
    return profile_entity_choices(hass, field, profile_entry_id)


def _number_or_entity_selector(
    hass, field: str, profile_entry_id: str | None = None
):
    """Dropdown compatible entities while still permitting a manual number/ID."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_compatible_profile_entities(hass, field, profile_entry_id),
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _normalize_sex(value):
    """Collapse legacy non-binary/withheld choices to one unused backend value."""
    return "prefer_not_to_say" if value == "other" else value


def _sex_selector():
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=["female", "male", "prefer_not_to_say"],
            translation_key="sex",
        )
    )


def _optional_suggested(key, value=None):
    """Show a current/recommended value without making it impossible to clear."""
    if value in (None, "", []):
        return vol.Optional(key)
    return vol.Optional(key, description={"suggested_value": value})


def _device_multi():
    """Legacy unrestricted device selector kept for migrations/tests."""
    return selector.DeviceSelector(selector.DeviceSelectorConfig(multiple=True))


def _supported_device_multi(choices):
    """Select only devices proven parseable by the runtime capability catalog."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[item.as_selector_option() for item in choices],
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _choice_ids(choices) -> list[str]:
    return [item.value for item in choices]


def _area_multi():
    return selector.AreaSelector(
        selector.AreaSelectorConfig(
            multiple=True,
        )
    )


def _entity_multi(domain):
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=domain,
            multiple=True,
        )
    )


def _entity_single(domain):
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=domain,
            multiple=False,
        )
    )


def _cast_media_player_single():
    """Select a Google Cast media-player entity for the TV dashboard."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="media_player",
            integration="cast",
            multiple=False,
        )
    )


def _preferred_ai_task_entity(hass):
    """Return Home Assistant's current preferred data-generation AI Task."""
    preferences = hass.data.get(AI_TASK_DATA_PREFERENCES)
    entity_id = getattr(preferences, "gen_data_entity_id", None)
    return str(entity_id) if entity_id else None


def _ai_entity_label(hass, entity_id: str) -> str:
    """Return a readable provider label while keeping the entity ID visible."""
    state = hass.states.get(entity_id)
    if state is None:
        return entity_id
    name = str(getattr(state, "name", "") or entity_id)
    return entity_id if name == entity_id else f"{name} ({entity_id})"


def _ai_entity(hass, current: str | None = None):
    """Select the HA default AI Task or pin Fitness to a specific provider."""
    preferred = _preferred_ai_task_entity(hass)
    default_label = "Home Assistant"
    if preferred:
        default_label += f" — {_ai_entity_label(hass, preferred)}"

    options = [
        {
            "value": AI_ENTITY_SYSTEM_DEFAULT,
            "label": default_label,
        }
    ]
    seen = {AI_ENTITY_SYSTEM_DEFAULT}
    for state in sorted(hass.states.async_all(), key=lambda item: item.entity_id):
        if not state.entity_id.startswith(("ai_task.", "conversation.")):
            continue
        seen.add(state.entity_id)
        options.append(
            {
                "value": state.entity_id,
                "label": _ai_entity_label(hass, state.entity_id),
            }
        )

    # Keep a previously selected provider editable even if it is currently
    # unavailable or has been removed from the state machine. Runtime will
    # surface a repair and temporarily fall back to the HA default AI Task.
    if current and current not in seen:
        options.append({"value": current, "label": current})

    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _number(min_v, max_v, *, step=1):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v,
            max=max_v,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _weight_scale_selector(hass, current: str | None = None):
    """Offer only plausible weight sensors; a scale entity is never free text."""
    options = list(weight_scale_entity_choices(hass))
    current = str(current or "").strip()
    if current and current not in {item["value"] for item in options}:
        # Preserve an existing configuration even while its entity is temporarily
        # unavailable; new selections remain restricted to discovered choices.
        options.append({"value": current, "label": current})
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            custom_value=False,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _resolved_weight_default(hass, raw):
    """Turn an old number/entity default into a numeric manual current weight."""
    resolved = resolve_number_or_entity(hass, raw, quantity="weight").value
    if resolved is None:
        return None
    try:
        value = float(resolved)
    except (TypeError, ValueError):
        return None
    return round(value, 1) if 20 <= value <= 500 else None


def _validate_manual_weight(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return 20 <= number <= 500


def _validate_weight_scale(hass, value) -> bool:
    if value in (None, ""):
        return True
    return weight_scale_entity_supported(hass, str(value).strip())


def _validate(hass, user_input, specs, profile_entry_id: str | None = None):
    errors = {}
    for key, (minimum, maximum, required) in specs.items():
        value = user_input.get(key)
        if not validate_number_or_entity(
            value,
            min_value=minimum,
            max_value=maximum,
            required=required,
        ):
            errors[key] = "invalid_number_or_entity"
            continue
        if is_entity_reference(value):
            entity_id = str(value).strip()
            supported = {
                item["value"]
                for item in profile_entity_choices(hass, key, profile_entry_id)
            }
            if entity_id not in supported and not profile_entity_supported(
                hass, key, entity_id, profile_entry_id
            ):
                errors[key] = "invalid_number_or_entity"
    return errors




def _preferred_profile_tts_entity(hass, language: str | None) -> str | None:
    """Auto-select local Piper/Wyoming TTS for the Fitness profile language."""
    desired = str(language or "en").lower().split("-", 1)[0].split("_", 1)[0]
    registry = er.async_get(hass)
    ranked: list[tuple[int, str]] = []
    for state in hass.states.async_all("tts"):
        if state.state == "unavailable":
            continue
        supported = state.attributes.get("supported_languages")
        if isinstance(supported, (list, tuple)) and supported:
            if not any(
                str(item).lower() == desired
                or str(item).lower().startswith(desired + "-")
                or str(item).lower().startswith(desired + "_")
                for item in supported
            ):
                continue
        entry = registry.async_get(state.entity_id)
        platform = str(entry.platform or "") if entry is not None else ""
        label = f"{state.entity_id} {state.attributes.get('friendly_name') or ''}".lower()
        if "piper" in label:
            ranked.append((500, state.entity_id))
        elif platform == "wyoming":
            ranked.append((400, state.entity_id))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1]

def _dashboard_module_selector():
    """Return presentation-only dashboard modules; no module starts polling."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(DASHBOARD_MODULES),
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key="dashboard_module",
        )
    )


def _dashboard_theme_selector():
    """Allow an existing HA theme name while keeping the system default safe."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": "default", "label": "Home Assistant"},
                {"value": "fitness_performance", "label": "Fitness · Performance"},
                {"value": "fitness_minimal", "label": "Fitness · Minimal"},
                {"value": "fitness_oled", "label": "Fitness · OLED"},
                {"value": "fitness_glass", "label": "Fitness · Glass"},
                {"value": "fitness_classic", "label": "Fitness · Classic"},
            ],
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _about_payload() -> tuple[str, str]:
    """Read bounded local release metadata without network work."""
    base = Path(__file__).resolve().parent
    version = "unknown"
    try:
        manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        version = str(manifest.get("version") or version)
    except (OSError, ValueError, TypeError):
        pass
    changelog = "Changelog is unavailable in this installation."
    try:
        text = (base / "changelog.md").read_text(encoding="utf-8")
        # Config-flow descriptions should stay bounded on phones. Keep the current
        # Unreleased section rather than pushing the entire historical changelog.
        end = text.find("\n## ", text.find("## Unreleased") + 3)
        if end > 0:
            text = text[:end]
        changelog = text.strip()[:12_000]
    except OSError:
        pass
    return version, changelog


class FitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 14

    def __init__(self):
        self._data = {}
        self._autofill_defaults: dict[str, str] | None = None
        self._first_install_choice = False

    def _profile_autofill(self) -> dict[str, str]:
        if self._autofill_defaults is None:
            self._autofill_defaults = exact_profile_defaults(self.hass)
        return self._autofill_defaults

    async def async_step_integration_discovery(self, discovery_info):
        """Create Local Sensors infrastructure or assign a discovered sensor."""
        if bool((discovery_info or {}).get("devices_hub")):
            await self.async_set_unique_id("fitness_devices")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Fitness Devices",
                data={"entry_type": "devices_hub"},
            )
        if bool((discovery_info or {}).get("live_hub")):
            await self.async_set_unique_id("local_sensors")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Fitness Protocols",
                data={"entry_type": "live_hub"},
            )

        sensor_id = str((discovery_info or {}).get("sensor_id", "")).strip()
        if not sensor_id:
            return self.async_abort(reason="invalid_discovery")

        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        sensor_id = runtime.resolve_sensor_id(sensor_id)
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None:
            return self.async_abort(reason="sensor_unavailable")
        if runtime.sensor_is_accepted(sensor_id):
            return self.async_abort(reason="live_sensor_assigned")

        self._discovery_sensor_id = sensor_id
        # Give the discovery card a useful title instead of the generic Fitness
        # integration title. With no flow_title defined, HA uses {name} directly.
        self.context["title_placeholders"] = {"name": sensor.discovery_name()}
        await self.async_set_unique_id(f"live_sensor:{sensor_id}")
        return await self.async_step_assign_live_sensor()

    async def async_step_assign_live_sensor(self, user_input=None):
        """Choose every Fitness profile allowed to use a discovered sensor."""
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        sensor_id = getattr(self, "_discovery_sensor_id", None)
        sensor_id = runtime.resolve_sensor_id(sensor_id) if sensor_id else None
        self._discovery_sensor_id = sensor_id
        sensor = runtime.sensors.get(sensor_id) if sensor_id else None
        if sensor is None:
            return self.async_abort(reason="sensor_unavailable")
        if runtime.sensor_is_accepted(sensor_id):
            return self.async_abort(reason="live_sensor_assigned")
        # The other radio can be discovered while this flow is already open. Keep
        # the title truthful if a provisional BT/ANT+ sensor becomes dual-transport.
        self.context["title_placeholders"] = {"name": sensor.discovery_name()}

        # Snapshot profile entries: accepting a sensor updates/reloads profile
        # config entries, which mutates runtime.profile_entries asynchronously.
        # Never iterate the live mapping while applying assignments.
        profile_entries = list(runtime.profile_entries.values())
        profiles = [
            {"value": entry.entry_id, "label": entry.title}
            for entry in profile_entries
        ]
        if not profiles:
            return self.async_abort(reason="no_fitness_profiles")

        if user_input is not None:
            selected_profiles = set(user_input.get("fitness_profile_ids") or [])
            smart_archive = is_smart_workout_candidate(sensor)
            if smart_archive and len(selected_profiles) > 1:
                return self.async_show_form(
                    step_id="assign_live_sensor",
                    data_schema=vol.Schema(
                        {
                            vol.Required("fitness_profile_ids"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=profiles,
                                    multiple=True,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            )
                        }
                    ),
                    errors={"base": "select_smart_device_owner"},
                    description_placeholders={"sensor": sensor.label()},
                )
            if not selected_profiles:
                return self.async_show_form(
                    step_id="assign_live_sensor",
                    data_schema=vol.Schema(
                        {
                            vol.Required("fitness_profile_ids"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=profiles,
                                    multiple=True,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            )
                        }
                    ),
                    errors={"base": "select_profile"},
                    description_placeholders={"sensor": sensor.label()},
                )

            pending_updates: list[tuple[str, dict]] = []
            for entry in profile_entries:
                raw_ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
                ids = []
                for configured_id in raw_ids:
                    canonical_id = runtime.resolve_sensor_id(configured_id)
                    if canonical_id not in ids:
                        ids.append(canonical_id)
                if entry.entry_id in selected_profiles and sensor_id not in ids:
                    ids.append(sensor_id)
                elif entry.entry_id not in selected_profiles and sensor_id in ids:
                    ids.remove(sensor_id)
                options = dict(entry.options)
                options[CONF_LIVE_SENSOR_IDS] = ids
                if options != dict(entry.options):
                    pending_updates.append((entry.entry_id, options))

            # A local workout archive belongs to one person even though its live
            # HR/power capabilities may later be shared across profiles. The normal
            # discovery flow therefore establishes one archive owner immediately.
            if is_smart_workout_candidate(sensor) and selected_profiles:
                owner_profile_id = next(iter(selected_profiles))
                runtime.configure_smart_workout_device(
                    sensor_id,
                    owner_profile_id=owner_profile_id,
                    device_type=smart_workout_device_type(sensor),
                    model_label=smart_workout_model_label(sensor),
                )

            # Acceptance is committed in memory immediately so a racing radio packet
            # cannot create another discovery flow. Profile Live infrastructure is
            # stable, so assignment persists routing only and never reloads profiles.
            runtime.mark_sensor_accepted(sensor_id)

            async def _finalize_assignment() -> None:
                # Let the config-flow response reach the frontend before doing Device
                # Registry materialization. ConfigEntry updates are persisted with the
                # reload listener suppressed because assignment is data routing only.
                await asyncio.sleep(0.5)
                changed_entries: list[str] = []
                for entry_id, options in pending_updates:
                    entry = self.hass.config_entries.async_get_entry(entry_id)
                    if entry is None:
                        continue
                    if getattr(getattr(entry, "state", None), "value", None) == "loaded":
                        runtime.suppress_entry_reload_once(entry_id)
                    self.hass.config_entries.async_update_entry(entry, options=options)
                    changed_entries.append(entry_id)

                canonical_id = runtime.resolve_sensor_id(sensor_id)
                runtime.finalize_sensor_acceptance(canonical_id)
                runtime.schedule_profile_assignment_refresh(changed_entries)
                runtime.notify_sensor_assignment_changed(canonical_id)

            self.hass.async_create_background_task(
                _finalize_assignment(),
                f"fitness finalize live sensor assignment {sensor_id}",
                eager_start=False,
            )
            return self.async_abort(reason="live_sensor_assigned")

        return self.async_show_form(
            step_id="assign_live_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("fitness_profile_ids"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=profiles,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"sensor": sensor.label()},
        )

    async def async_step_first_install(self, user_input=None):
        """Offer infrastructure or profile setup without doing radio work."""
        del user_input
        return self.async_show_menu(
            step_id="first_install",
            menu_options=["manage_protocols", "add_user"],
        )

    async def async_step_add_user(self, user_input=None):
        """Continue through the existing person/profile flow unchanged."""
        del user_input
        self._first_install_choice = True
        return await self.async_step_user()

    async def async_step_add_protocol(self, user_input=None):
        """Backward-compatible alias for the protocol manager."""
        return await self.async_step_manage_protocols(user_input)

    async def async_step_manage_protocols(self, user_input=None):
        """Enable/remove protocol layers and choose hardware discovery policy."""
        from .live import get_live_runtime
        from .live.runtime import HUB_ENTRY_TYPE

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        existing_hub = next(
            (entry for entry in self.hass.config_entries.async_entries(DOMAIN)
             if entry.data.get("entry_type") == HUB_ENTRY_TYPE),
            None,
        )
        if user_input is not None:
            selected = {
                transport for transport in ("bluetooth", "antplus")
                if bool(user_input.get(transport, False))
            }
            automatic = {
                transport: bool(user_input.get(f"{transport}_automatic_hardware", True))
                for transport in selected
            }
            self._pending_protocol_selection = selected
            self._pending_protocol_automatic = automatic
            self._protocol_manual_transports = [t for t in selected if not automatic[t]]
            self._existing_protocol_hub_id = existing_hub.entry_id if existing_hub else None
            if self._protocol_manual_transports:
                return await self.async_step_manage_protocol_hardware()
            return await self._async_finish_manage_protocols({})

        return self.async_show_form(
            step_id="manage_protocols",
            data_schema=vol.Schema({
                vol.Required("bluetooth", default=runtime.adapter_configured("bluetooth")): bool,
                vol.Required(
                    "bluetooth_automatic_hardware",
                    default=runtime.adapter_automatic_hardware("bluetooth"),
                ): bool,
                vol.Required("antplus", default=runtime.adapter_configured("antplus")): bool,
                vol.Required(
                    "antplus_automatic_hardware",
                    default=runtime.adapter_automatic_hardware("antplus"),
                ): bool,
            }),
        )

    async def async_step_manage_protocol_hardware(self, user_input=None):
        """Native menu for manual hardware discovery/selection."""
        del user_input
        return self.async_show_menu(
            step_id="manage_protocol_hardware",
            menu_options=["discover_protocol_hardware", "select_protocol_hardware"],
        )

    async def async_step_discover_protocol_hardware(self, user_input=None):
        """Run one bounded scan and return to manual hardware management."""
        del user_input
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        for transport in list(getattr(self, "_protocol_manual_transports", []) or []):
            runtime.begin_manual_scan_window(transport, 20.0)
            if transport == "bluetooth":
                provider = runtime.providers.get("bluetooth")
                refresh = getattr(provider, "async_refresh_discovery", None)
                if callable(refresh):
                    try:
                        await refresh()
                    except Exception:  # best-effort discovery must not break setup
                        pass
        return await self.async_step_manage_protocol_hardware()

    async def async_step_select_protocol_hardware(self, user_input=None):
        """Choose supported hardware for protocols using manual discovery."""
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        transports = list(getattr(self, "_protocol_manual_transports", []) or [])
        if user_input is not None:
            selected_hw = {
                transport: set(user_input.get(f"{transport}_hardware") or [])
                for transport in transports
            }
            return await self._async_finish_manage_protocols(selected_hw)
        schema = {}
        for transport in transports:
            schema[vol.Required(
                f"{transport}_hardware",
                default=sorted(runtime.selected_receiver_ids(transport)),
            )] = selector.SelectSelector(selector.SelectSelectorConfig(
                options=runtime.transport_hardware_choices(transport),
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            ))
        return self.async_show_form(
            step_id="select_protocol_hardware",
            data_schema=vol.Schema(schema),
        )

    async def _async_finish_manage_protocols(self, selected_hw: dict[str, set[str]]):
        """Apply protocol state or create the shared Fitness Protocols service."""
        from .live import get_live_runtime
        from .live.runtime import HUB_ENTRY_TYPE
        runtime = get_live_runtime(self.hass)
        selected = set(getattr(self, "_pending_protocol_selection", set()) or set())
        automatic = dict(getattr(self, "_pending_protocol_automatic", {}) or {})
        existing_hub = next(
            (entry for entry in self.hass.config_entries.async_entries(DOMAIN)
             if entry.data.get("entry_type") == HUB_ENTRY_TYPE),
            None,
        )
        if existing_hub is not None:
            await runtime.async_set_protocol_selection(selected)
            for transport in selected:
                await runtime.async_set_hardware_selection(
                    transport,
                    automatic=automatic.get(transport, True),
                    selected=selected_hw.get(transport),
                )
            return self.async_abort(reason="protocols_updated")
        await self.async_set_unique_id("local_sensors")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Fitness Protocols",
            data={
                "entry_type": "live_hub",
                "initial_protocols": sorted(selected),
                "initial_hardware": {
                    transport: {
                        "automatic": automatic.get(transport, True),
                        "selected": sorted(selected_hw.get(transport, set())),
                    } for transport in selected
                },
            },
        )

    async def async_step_user(self, user_input=None):
        if user_input is None and not self._first_install_choice:
            # Every explicit Add Integration action starts at the same friendly
            # choice: connect devices or create another profile. Discovery and
            # reconfigure sources use their dedicated steps and never hit here.
            return await self.async_step_first_install()
        errors = {}
        if user_input is not None:
            try:
                dob = date(
                    int(user_input[CONF_BIRTH_YEAR]),
                    int(user_input[CONF_BIRTH_MONTH]),
                    int(user_input[CONF_BIRTH_DAY]),
                )
                if dob >= date.today():
                    errors["base"] = "invalid_date"
                else:
                    self._data.update(user_input)
                    self._data[CONF_DATE_OF_BIRTH] = dob.isoformat()
                    for key in (CONF_BIRTH_DAY, CONF_BIRTH_MONTH, CONF_BIRTH_YEAR):
                        self._data.pop(key, None)
                    return await self.async_step_required()
            except (TypeError, ValueError):
                errors["base"] = "invalid_date"

        schema = vol.Schema(
            {
                vol.Required(CONF_PROFILE_NAME): str,
                vol.Required(
                    CONF_LANGUAGE,
                    default=_default_language(self.hass),
                ): _language_selector(),
                vol.Required(CONF_BIRTH_DAY, default=1): _number(1, 31),
                vol.Required(CONF_BIRTH_MONTH, default="1"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[str(i) for i in range(1, 13)],
                        translation_key="birth_month",
                    )
                ),
                vol.Required(CONF_BIRTH_YEAR, default=1980): _number(1900, date.today().year),
                vol.Optional(CONF_SEX): _sex_selector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_required(self, user_input=None):
        errors = {}
        if user_input is not None:
            if not _validate_manual_weight(user_input.get(CONF_WEIGHT)):
                errors[CONF_WEIGHT] = "invalid_number_or_entity"
            if not _validate_weight_scale(self.hass, user_input.get(CONF_WEIGHT_SCALE_ENTITY)):
                errors[CONF_WEIGHT_SCALE_ENTITY] = "invalid_number_or_entity"
            errors.update(
                _validate(
                    self.hass,
                    user_input,
                    {CONF_RESTING_HR: (20, 150, False)},
                )
            )
            if not errors:
                self._data.update(
                    {k: v for k, v in user_input.items() if v not in (None, "")}
                )
                return await self.async_step_optional()

        autofill = self._profile_autofill()
        weight_default = _resolved_weight_default(self.hass, autofill.get(CONF_WEIGHT))
        weight_key = (
            vol.Required(CONF_WEIGHT, default=weight_default)
            if weight_default is not None
            else vol.Required(CONF_WEIGHT)
        )
        return self.async_show_form(
            step_id="required",
            data_schema=vol.Schema(
                {
                    weight_key: _number(20, 500, step=0.1),
                    vol.Optional(CONF_WEIGHT_SCALE_ENTITY): _weight_scale_selector(self.hass),
                    _optional_suggested(
                        CONF_RESTING_HR, autofill.get(CONF_RESTING_HR)
                    ): _number_or_entity_selector(self.hass, CONF_RESTING_HR),
                }
            ),
            errors=errors,
        )

    async def async_step_optional(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate(
                self.hass,
                user_input,
                {
                    CONF_HEIGHT: (50, 260, False),
                    CONF_MAX_HR: (60, 260, False),
                    CONF_VO2MAX: (5, 100, False),
                    CONF_THRESHOLD_HR: (60, 260, False),
                    CONF_THRESHOLD_PACE: (1, 20, False),
                    CONF_THRESHOLD_POWER: (20, 2500, False),
                },
            )
            if not errors:
                self._data.update(
                    {k: v for k, v in user_input.items() if v not in (None, "")}
                )
                return await self._async_next_live_setup_step()

        autofill = self._profile_autofill()
        return self.async_show_form(
            step_id="optional",
            data_schema=vol.Schema(
                {
                    _optional_suggested(CONF_HEIGHT, autofill.get(CONF_HEIGHT)): _number_or_entity_selector(self.hass, CONF_HEIGHT),
                    _optional_suggested(CONF_MAX_HR, autofill.get(CONF_MAX_HR)): _number_or_entity_selector(self.hass, CONF_MAX_HR),
                    _optional_suggested(CONF_VO2MAX, autofill.get(CONF_VO2MAX)): _number_or_entity_selector(self.hass, CONF_VO2MAX),
                    _optional_suggested(CONF_THRESHOLD_HR, autofill.get(CONF_THRESHOLD_HR)): _number_or_entity_selector(self.hass, CONF_THRESHOLD_HR),
                    _optional_suggested(CONF_THRESHOLD_PACE, autofill.get(CONF_THRESHOLD_PACE)): _number_or_entity_selector(self.hass, CONF_THRESHOLD_PACE),
                    _optional_suggested(CONF_THRESHOLD_POWER, autofill.get(CONF_THRESHOLD_POWER)): _number_or_entity_selector(self.hass, CONF_THRESHOLD_POWER),
                }
            ),
            errors=errors,
        )


    async def _async_next_live_setup_step(self):
        """Skip native sensor selection until an adapter is explicitly enabled."""
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if runtime.live_surface_available:
            return await self.async_step_live_devices()
        return await self.async_step_workout_devices()

    async def async_step_live_devices(self, user_input=None):
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if user_input is not None:
            await runtime.async_end_setup_discovery()
            self._data[CONF_LIVE_SENSOR_IDS] = list(
                user_input.get(CONF_LIVE_SENSOR_IDS) or []
            )
            generic_ids = list(user_input.get(CONF_LIVE_DEVICE_IDS) or [])
            if generic_ids:
                self._data[CONF_LIVE_DEVICE_IDS] = generic_ids
            return await self.async_step_workout_devices()

        if not getattr(self, "_native_live_scan_started", False):
            await runtime.async_begin_setup_discovery()
            self._native_live_scan_started = True
            # ANT+ has no advertisement cache: give broadcasting sensors a short
            # window to appear before constructing the selector. BLE meanwhile
            # uses HA's already-cached service advertisements immediately.
            await asyncio.sleep(2.5)
        choices = [
            {"value": sensor.sensor_id, "label": sensor.label()}
            for sensor in runtime.sensors.values()
            if runtime.sensor_is_accepted(sensor.sensor_id)
            and any(runtime.adapter_present(t) for t in sensor.transports)
        ]
        return self.async_show_form(
            step_id="live_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LIVE_SENSOR_IDS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_LIVE_DEVICE_IDS): _supported_device_multi(
                        live_device_choices(self.hass)
                    ),
                }
            ),
        )

    async def async_step_workout_devices(self, user_input=None):
        if user_input is not None:
            ids = list(user_input.get(CONF_WORKOUT_DEVICE_IDS) or [])
            if ids:
                self._data[CONF_WORKOUT_DEVICE_IDS] = ids
            self._data[CONF_DETAILED_STRENGTH_ANALYSIS] = bool(
                user_input.get(CONF_DETAILED_STRENGTH_ANALYSIS, False)
            )
            self._data[CONF_WORKOUT_RETENTION_DAYS] = int(
                user_input.get(CONF_WORKOUT_RETENTION_DAYS, DEFAULT_WORKOUT_RETENTION_DAYS)
            )
            self._data[CONF_FIT_FILE_RETENTION_COUNT] = int(
                user_input.get(CONF_FIT_FILE_RETENTION_COUNT, DEFAULT_FIT_FILE_RETENTION_COUNT)
            )
            return await self.async_step_sleep_devices()

        workout_choices = workout_device_choices(self.hass)
        return self.async_show_form(
            step_id="workout_devices",
            data_schema=vol.Schema(
                {
                    _optional_suggested(
                        CONF_WORKOUT_DEVICE_IDS, _choice_ids(workout_choices)
                    ): _supported_device_multi(workout_choices),
                    vol.Optional(CONF_DETAILED_STRENGTH_ANALYSIS, default=False): bool,
                    vol.Required(CONF_WORKOUT_RETENTION_DAYS, default=DEFAULT_WORKOUT_RETENTION_DAYS): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=MAX_WORKOUT_RETENTION_DAYS, step=1,
                            unit_of_measurement="d", mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_FIT_FILE_RETENTION_COUNT, default=DEFAULT_FIT_FILE_RETENTION_COUNT): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=500, step=1, mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_history(self, user_input=None):
        """Configure canonical workout-history retention."""
        if user_input is not None:
            self._data[CONF_WORKOUT_RETENTION_DAYS] = int(
                user_input.get(
                    CONF_WORKOUT_RETENTION_DAYS,
                    DEFAULT_WORKOUT_RETENTION_DAYS,
                )
            )
            return await self.async_step_sleep_devices()
        return self.async_show_form(
            step_id="history",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WORKOUT_RETENTION_DAYS,
                        default=DEFAULT_WORKOUT_RETENTION_DAYS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=MAX_WORKOUT_RETENTION_DAYS,
                            step=1,
                            unit_of_measurement="d",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )

    async def async_step_sleep_devices(self, user_input=None):
        if user_input is not None:
            ids = list(user_input.get(CONF_SLEEP_DEVICE_IDS) or [])
            if ids:
                self._data[CONF_SLEEP_DEVICE_IDS] = ids
            return await self.async_step_ai()
        sleep_choices = sleep_device_choices(self.hass)
        return self.async_show_form(
            step_id="sleep_devices",
            data_schema=vol.Schema(
                {
                    _optional_suggested(
                        CONF_SLEEP_DEVICE_IDS, _choice_ids(sleep_choices)
                    ): _supported_device_multi(sleep_choices)
                }
            ),
        )

    async def async_step_ai(self, user_input=None):
        if user_input is not None:
            self._data.update(
                {k: v for k, v in user_input.items() if v not in (None, "")}
            )
            return await self.async_step_feedback()

        ai_available = bool(
            self.hass.services.has_service("ai_task", "generate_data")
            or any(
                state.entity_id.startswith(("ai_task.", "conversation."))
                for state in self.hass.states.async_all()
            )
        )

        schema = {
            vol.Optional(CONF_AI_ENABLED, default=ai_available): bool,
            _optional_suggested(
                CONF_AI_ENTITY, AI_ENTITY_SYSTEM_DEFAULT
            ): _ai_entity(self.hass),
            vol.Optional(CONF_TRAINING_GOAL): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            vol.Optional(CONF_TRAINING_GOAL_DATE): selector.DateSelector(),
            vol.Optional(CONF_TRAINING_DAYS_PER_WEEK, default=4): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=7, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        return self.async_show_form(
            step_id="ai",
            data_schema=vol.Schema(schema),
        )


    async def async_step_feedback(self, user_input=None):
        """Configure audiovisual live coaching and post-workout messaging."""
        if user_input is not None:
            self._data.update(
                {
                    key: value
                    for key, value in user_input.items()
                    if value not in (None, "", [])
                }
            )

            return await self.async_step_tv_dashboard()

        default_tts = _preferred_profile_tts_entity(
            self.hass, self._data.get(CONF_LANGUAGE) or "en"
        )

        schema = {
            vol.Optional(CONF_FEEDBACK_AREA_IDS): _area_multi(),
            vol.Optional(CONF_FEEDBACK_LIGHT_IDS): _entity_multi("light"),
            vol.Optional(CONF_NOTIFY_ENTITY_IDS): _entity_multi("notify"),
        }

        schema[
            vol.Optional(
                CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
                default=False,
            )
        ] = bool
        schema[
            vol.Optional(
                CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
                default=5,
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=120,
                step=1,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        if default_tts:
            schema[
                _optional_suggested(
                    CONF_TTS_ENTITY_ID, default_tts
                )
            ] = _entity_single("tts")
        else:
            schema[vol.Optional(CONF_TTS_ENTITY_ID)] = _entity_single("tts")

        schema[
            vol.Optional(CONF_TTS_MEDIA_PLAYER_IDS)
        ] = _entity_multi("media_player")

        return self.async_show_form(
            step_id="feedback",
            data_schema=vol.Schema(schema),
        )

    async def async_step_tv_dashboard(self, user_input=None):
        """Configure the optional full-screen Fitness TV dashboard."""
        if user_input is not None:
            self._data[CONF_TV_DASHBOARD_ENABLED] = bool(
                user_input.get(CONF_TV_DASHBOARD_ENABLED, False)
            )
            self._data[CONF_TV_DUCKING_PERCENT] = int(
                user_input.get(
                    CONF_TV_DUCKING_PERCENT,
                    DEFAULT_TV_DUCKING_PERCENT,
                )
            )
            self._data[CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE] = bool(
                user_input.get(
                    CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                    DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                )
            )
            target = str(user_input.get(CONF_TV_MEDIA_PLAYER_ID) or "").strip()
            if target:
                self._data[CONF_TV_MEDIA_PLAYER_ID] = target

            name = self._data[CONF_PROFILE_NAME]
            await self.async_set_unique_id(
                f"fitness_{name.strip().lower().replace(' ', '_')}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data=self._data)

        schema = {
            vol.Optional(CONF_TV_DASHBOARD_ENABLED, default=False): bool,
            vol.Optional(
                CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                default=DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
            ): bool,
            vol.Optional(CONF_TV_MEDIA_PLAYER_ID): _cast_media_player_single(),
            vol.Optional(
                CONF_TV_DUCKING_PERCENT,
                default=DEFAULT_TV_DUCKING_PERCENT,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
        return self.async_show_form(
            step_id="tv_dashboard",
            data_schema=vol.Schema(schema),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FitnessOptionsFlow()


class FitnessOptionsFlow(config_entries.OptionsFlow):
    """Edit every Fitness configuration value."""

    def _current(self):
        return {
            **self.config_entry.data,
            **self.config_entry.options,
        }

    async def _save_merge(self, values):
        options = dict(self.config_entry.options)
        options.update(values)
        return self.async_create_entry(
            title="",
            data=options,
        )

    async def async_step_init(self, user_input=None):
        from .live import get_live_runtime
        from .live.runtime import HUB_ENTRY_TYPE
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if self.config_entry.data.get("entry_type") == HUB_ENTRY_TYPE:
            menu_options=["sensor_assignments"]
            menu_options = ["protocols", *menu_options, "about"]
            return self.async_show_menu(
                step_id="init",
                menu_options=menu_options,
            )
        menu = ["profile", "fitness_inputs"]
        if runtime.live_surface_available:
            menu.append("live_devices")
        menu.extend(["workout_devices", "sleep_devices", "ai", "feedback", "tv_dashboard"])
        menu.insert(menu.index("workout_devices") + 1, "smart_workout_devices")
        menu.insert(menu.index("tv_dashboard"), "features")
        menu.append("about")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_protocols(self, user_input=None):
        """Manage Fitness protocols as one transactional configuration change."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if user_input is not None:
            selected = {
                transport
                for transport in ("bluetooth", "antplus")
                if bool(user_input.get(transport, False))
            }
            automatic = {
                transport: bool(user_input.get(f"{transport}_automatic_hardware", True))
                for transport in selected
            }
            # Do not mutate the live runtime while the user is navigating the
            # Discover/Select hardware substeps.  Keep one staged transaction so
            # Back never resurrects the previously persisted automatic setting.
            self._pending_protocol_selection = selected
            self._pending_protocol_automatic = automatic
            self._pending_protocol_hardware = {
                transport: set(runtime.selected_receiver_ids(transport))
                for transport in selected
            }
            self._protocol_manual_transports = [
                transport for transport in selected if not automatic[transport]
            ]
            if self._protocol_manual_transports:
                return await self.async_step_protocol_hardware()
            return await self._async_finish_protocol_options({})

        pending_selected = getattr(self, "_pending_protocol_selection", None)
        pending_automatic = getattr(self, "_pending_protocol_automatic", None)
        return self.async_show_form(
            step_id="protocols",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "bluetooth",
                        default=(
                            "bluetooth" in pending_selected
                            if pending_selected is not None
                            else runtime.adapter_configured("bluetooth")
                        ),
                    ): bool,
                    vol.Required(
                        "bluetooth_automatic_hardware",
                        default=(
                            bool(pending_automatic.get("bluetooth", True))
                            if pending_automatic is not None and "bluetooth" in (pending_selected or set())
                            else runtime.adapter_automatic_hardware("bluetooth")
                        ),
                    ): bool,
                    vol.Required(
                        "antplus",
                        default=(
                            "antplus" in pending_selected
                            if pending_selected is not None
                            else runtime.adapter_configured("antplus")
                        ),
                    ): bool,
                    vol.Required(
                        "antplus_automatic_hardware",
                        default=(
                            bool(pending_automatic.get("antplus", True))
                            if pending_automatic is not None and "antplus" in (pending_selected or set())
                            else runtime.adapter_automatic_hardware("antplus")
                        ),
                    ): bool,
                }
            ),
        )

    async def async_step_protocol_hardware(self, user_input=None):
        """Offer a native Discover now action before manual hardware selection."""
        del user_input
        return self.async_show_menu(
            step_id="protocol_hardware",
            menu_options=["protocol_hardware_discover", "protocol_hardware_select"],
        )

    async def async_step_protocol_hardware_discover(self, user_input=None):
        """Run one bounded discovery pass for manually managed protocols."""
        del user_input
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        for transport in list(getattr(self, "_protocol_manual_transports", []) or []):
            runtime.begin_manual_scan_window(transport, 20.0)
            if transport == "bluetooth":
                provider = runtime.providers.get("bluetooth")
                refresh = getattr(provider, "async_refresh_discovery", None)
                if callable(refresh):
                    try:
                        await refresh()
                    except Exception:
                        pass
        return await self.async_step_protocol_hardware()

    async def async_step_protocol_hardware_select(self, user_input=None):
        """Select concrete supported hardware when automatic discovery is disabled."""
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        transports = list(getattr(self, "_protocol_manual_transports", []) or [])
        if not transports:
            return await self.async_step_init()
        if user_input is not None:
            selected_hw = {
                transport: set(user_input.get(f"{transport}_hardware") or [])
                for transport in transports
            }
            return await self._async_finish_protocol_options(selected_hw)
        schema = {}
        for transport in transports:
            schema[vol.Required(
                f"{transport}_hardware",
                default=sorted(runtime.selected_receiver_ids(transport)),
            )] = selector.SelectSelector(selector.SelectSelectorConfig(
                options=runtime.transport_hardware_choices(transport),
                multiple=True, mode=selector.SelectSelectorMode.DROPDOWN,
            ))
        return self.async_show_form(
            step_id="protocol_hardware_select", data_schema=vol.Schema(schema),
        )

    async def _async_finish_protocol_options(self, selected_hw: dict[str, set[str]]):
        """Atomically commit the staged protocol + hardware policy transaction."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        selected = set(getattr(self, "_pending_protocol_selection", set()) or set())
        automatic = dict(getattr(self, "_pending_protocol_automatic", {}) or {})
        staged_hw = dict(getattr(self, "_pending_protocol_hardware", {}) or {})
        staged_hw.update(selected_hw)

        # Defer the hub reload until every policy value has been persisted. This
        # avoids reloading Fitness Protocols halfway through an OptionsFlow.
        await runtime.async_set_protocol_selection(selected, reload=False)
        for transport in selected:
            is_automatic = bool(automatic.get(transport, True))
            await runtime.async_set_hardware_selection(
                transport,
                automatic=is_automatic,
                selected=() if is_automatic else staged_hw.get(transport, set()),
            )
        await runtime.async_refresh_modules()
        runtime.request_hub_reload()

        self._protocol_manual_transports = []
        self._pending_protocol_selection = None
        self._pending_protocol_automatic = None
        self._pending_protocol_hardware = None
        return await self.async_step_init()

    async def async_step_features(self, user_input=None):
        """Configure optional dashboard presentation without background work."""
        current = self._current()
        if user_input is not None:
            values = dict(user_input)
            values[CONF_DASHBOARD_MODULES] = list(
                dict.fromkeys(values.get(CONF_DASHBOARD_MODULES) or ["core"])
            )
            return await self._save_merge(values)

        return self.async_show_form(
            step_id="features",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DASHBOARD_MODULES,
                        default=current.get(CONF_DASHBOARD_MODULES, DEFAULT_DASHBOARD_MODULES),
                    ): _dashboard_module_selector(),
                    vol.Required(
                        CONF_DASHBOARD_THEME,
                        default=current.get(CONF_DASHBOARD_THEME, "default"),
                    ): _dashboard_theme_selector(),
                    vol.Optional(
                        CONF_DASHBOARD_RSS_ENTITY_IDS,
                        default=current.get(CONF_DASHBOARD_RSS_ENTITY_IDS, []),
                    ): _entity_multi("sensor"),
                    vol.Optional(
                        CONF_DASHBOARD_MUSIC_ENTITY_IDS,
                        default=current.get(CONF_DASHBOARD_MUSIC_ENTITY_IDS, []),
                    ): _entity_multi("media_player"),
                    vol.Optional(
                        CONF_DASHBOARD_LIGHT_ENTITY_IDS,
                        default=current.get(CONF_DASHBOARD_LIGHT_ENTITY_IDS, []),
                    ): _entity_multi("light"),
                    vol.Optional(
                        CONF_DASHBOARD_VIDEO_ENTITY_IDS,
                        default=current.get(CONF_DASHBOARD_VIDEO_ENTITY_IDS, []),
                    ): _entity_multi("media_player"),
                    vol.Optional(
                        CONF_DASHBOARD_WEATHER_ENTITY_ID,
                        description={"suggested_value": current.get(CONF_DASHBOARD_WEATHER_ENTITY_ID)},
                    ): _entity_single("weather"),
                }
            ),
        )

    async def async_step_about(self, user_input=None):
        """Show installed version and bundled changelog without internet access."""
        if user_input is not None:
            return await self.async_step_init()
        version, changelog = await self.hass.async_add_executor_job(_about_payload)
        return self.async_show_form(
            step_id="about",
            data_schema=vol.Schema({}),
            description_placeholders={"version": version, "changelog": changelog},
        )

    async def _async_prepare_smart_device_discovery(self, runtime) -> tuple[str, ...]:
        """Enable usable protocols and automatic discovery for this setup flow.

        Entering Smart Fitness Devices is an explicit request to discover hardware.
        If a locally available/configured protocol was left in manual-scan mode,
        restore automatic discovery so the just-added device remains discoverable
        after this bounded setup scan.  Never enable hardware that HA cannot see.
        """
        enabled: list[str] = []
        for transport in ("bluetooth", "antplus"):
            if not runtime.adapter_configured(transport):
                continue
            if not runtime.adapter_enabled(transport):
                await runtime.async_set_transport_enabled(transport, True)
            if not runtime.adapter_automatic_scan(transport):
                await runtime.async_set_automatic_scan(transport, True)
            runtime.begin_manual_scan_window(transport, 20.0)
            enabled.append(transport)
        return tuple(enabled)

    async def _async_refresh_smart_workout_discovery(self, runtime) -> None:
        """Request one bounded control-plane discovery sweep when available."""
        await self._async_prepare_smart_device_discovery(runtime)
        provider = runtime.providers.get("bluetooth")
        refresh = getattr(provider, "async_refresh_discovery", None) if provider else None
        if refresh is None:
            return
        try:
            async with asyncio.timeout(15.0):
                await refresh()
        except TimeoutError:
            pass

    def _smart_workout_status(self, runtime, sensor) -> tuple[str, str]:
        """Return one cheap control-plane status without opening Bluetooth."""
        sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
        details = runtime.sensor_detail_values.get(sensor_id, {}) or {}
        error = str(details.get("garmin_last_error") or "none")
        state = str(details.get("garmin_sync_state") or "idle")
        compatibility = smart_workout_archive_compatibility(sensor)
        if compatibility is False:
            return "unsupported", "unsupported_transport"
        if error == "pairing_required":
            return "action_needed", error
        if error == "unsupported_transport" or state == "unsupported":
            return "unsupported", error
        if state in {"connecting", "syncing", "waiting", "retrying"}:
            return state, error
        if state == "ready" or details.get("garmin_last_successful_sync"):
            return "ready", error
        if runtime.sensor_is_accepted(sensor_id):
            return "configured", error
        return "discovered", error

    def _smart_workout_choices(self, runtime) -> list[dict[str, str]]:
        """Build a bounded list of physical devices plus setup recipes."""
        choices: list[dict[str, str]] = []
        sensors = sorted(
            (sensor for sensor in runtime.sensors.values() if is_smart_workout_candidate(sensor)),
            key=lambda item: item.label().lower(),
        )
        for sensor in sensors[:MAX_SMART_WORKOUT_DEVICE_CHOICES]:
            sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
            owner_id = runtime.smart_device_owner_profile_id(sensor_id)
            owner = runtime.profile_entries.get(owner_id) if owner_id else None
            owner_label = owner.title if owner is not None else "unowned"
            vendor = smart_workout_vendor(sensor).title()
            model = smart_workout_model_label(sensor)
            status, _error = self._smart_workout_status(runtime, sensor)
            choices.append({
                "value": f"sensor:{sensor_id}",
                "label": f"{vendor} · {model} · {status.replace('_', ' ')} · {owner_label}",
            })
        # Vendor entries are fallback guides, never runtime protocol routing.
        for vendor in SUPPORTED_SETUP_VENDORS:
            choices.append({
                "value": f"vendor:{vendor.vendor_id}",
                "label": f"Setup {vendor.label} · guided connection",
            })
        return choices[: MAX_SMART_WORKOUT_DEVICE_CHOICES + len(SUPPORTED_SETUP_VENDORS)]

    async def async_step_smart_workout_devices(self, user_input=None):
        """Discover and configure direct smart fitness devices for this profile."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if user_input is None:
            await self._async_refresh_smart_workout_discovery(runtime)

        choices = self._smart_workout_choices(runtime)
        if user_input is not None:
            selected = str(user_input.get("smart_workout_device") or "")
            if selected.startswith("sensor:"):
                self._smart_workout_sensor_id = runtime.resolve_sensor_id(selected.split(":", 1)[1])
                return await self.async_step_smart_workout_device_setup()
            if selected.startswith("vendor:"):
                self._smart_workout_vendor_id = selected.split(":", 1)[1]
                return await self.async_step_smart_workout_vendor_setup()
            return self.async_show_form(
                step_id="smart_workout_devices",
                data_schema=vol.Schema({
                    vol.Required("smart_workout_device"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
                    )
                }),
                errors={"base": "sensor_unavailable"},
            )

        return self.async_show_form(
            step_id="smart_workout_devices",
            data_schema=vol.Schema({
                vol.Required("smart_workout_device"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }),
        )

    async def async_step_garmin_local_guide(self, user_input=None):
        """Backward-compatible entry point for pre-smart-device links."""
        return await self.async_step_smart_workout_devices(user_input)

    async def _async_commit_smart_workout_device(self, runtime, sensor_id: str) -> None:
        """Assign one physical archive device using detected metadata only."""
        sensor_id = runtime.resolve_sensor_id(sensor_id)
        sensor = runtime.sensors[sensor_id]
        current = self._current()
        ids = list(current.get(CONF_LIVE_SENSOR_IDS) or [])
        ids = [item for item in ids if runtime.resolve_sensor_id(str(item)) != sensor_id]
        ids.append(sensor_id)
        options = dict(self.config_entry.options)
        options[CONF_LIVE_SENSOR_IDS] = ids
        if getattr(getattr(self.config_entry, "state", None), "value", None) == "loaded":
            runtime.suppress_entry_reload_once(self.config_entry.entry_id)
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

        # Device type/model remain display metadata. Automatic detection is kept
        # unless the user previously chose a broad type in a vendor guide.
        requested_type = str(getattr(self, "_smart_workout_manual_type", "") or "")
        if requested_type not in DEVICE_TYPES:
            requested_type = smart_workout_device_type(sensor)
        runtime.configure_smart_workout_device(
            sensor_id,
            owner_profile_id=self.config_entry.entry_id,
            device_type=requested_type,
            model_label=smart_workout_model_label(sensor),
        )
        if not runtime.sensor_is_accepted(sensor_id):
            runtime.mark_sensor_accepted(sensor_id)

        async def _finalize() -> None:
            await asyncio.sleep(0.5)
            canonical = runtime.resolve_sensor_id(sensor_id)
            runtime.finalize_sensor_acceptance(canonical)
            runtime.schedule_profile_assignment_refresh([self.config_entry.entry_id])
            runtime.notify_sensor_assignment_changed(canonical)

        self.hass.async_create_background_task(
            _finalize(),
            f"fitness finalize smart workout device {sensor_id}",
            eager_start=False,
        )

    async def async_step_smart_workout_device_setup(self, user_input=None):
        """Assign a detected device automatically; ask only for real decisions."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        sensor_id = runtime.resolve_sensor_id(str(getattr(self, "_smart_workout_sensor_id", "")))
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None or not is_smart_workout_candidate(sensor):
            return self.async_abort(reason="sensor_unavailable")

        owner_id = runtime.smart_device_owner_profile_id(sensor_id)
        owner_entry = runtime.profile_entries.get(owner_id) if owner_id else None
        owner_label = owner_entry.title if owner_entry is not None else "—"
        vendor_id = smart_workout_vendor(sensor)
        detected_model = smart_workout_model_label(sensor)
        capabilities = ", ".join(smart_workout_capability_labels(sensor)) or "workout archive"

        # Reopening an already-owned device is a status/action view, not a form
        # asking the user to retype metadata Fitness already knows.
        if owner_id == self.config_entry.entry_id and runtime.sensor_is_accepted(sensor_id):
            status, error = self._smart_workout_status(runtime, sensor)
            if error == "pairing_required":
                return await self.async_step_smart_workout_pairing_help()
            return await self.async_step_smart_workout_device_ready()

        # The only normal setup choice is a real ownership conflict. Use a
        # dropdown instead of a boolean/text field so the consequence is clear.
        if owner_id and owner_id != self.config_entry.entry_id:
            if user_input is None:
                return self.async_show_form(
                    step_id="smart_workout_device_setup",
                    data_schema=vol.Schema({
                        vol.Required("smart_device_owner_action", default="keep_current"): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    {"value": "keep_current", "label": f"Keep stored workouts with {owner_label}"},
                                    {"value": "transfer_here", "label": f"Transfer stored workouts to {self.config_entry.title}"},
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        )
                    }),
                    description_placeholders={
                        "device": sensor.label(), "vendor": vendor_id.title(), "model": detected_model,
                        "capabilities": capabilities, "owner": owner_label,
                    },
                )
            action = str(user_input.get("smart_device_owner_action") or "keep_current")
            if action != "transfer_here":
                return await self.async_step_smart_workout_devices()

        await self._async_commit_smart_workout_device(runtime, sensor_id)
        self._smart_workout_sensor_id = runtime.resolve_sensor_id(sensor_id)
        return await self.async_step_smart_workout_device_ready()

    async def async_step_smart_workout_device_ready(self, user_input=None):
        """Show automatic setup status and route to help only when needed."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        sensor_id = runtime.resolve_sensor_id(str(getattr(self, "_smart_workout_sensor_id", "")))
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None:
            return await self.async_step_smart_workout_devices()
        _status, error = self._smart_workout_status(runtime, sensor)
        if error == "pairing_required":
            return await self.async_step_smart_workout_pairing_help()
        if user_input is not None:
            return await self.async_step_init()
        status, _error = self._smart_workout_status(runtime, sensor)
        return self.async_show_form(
            step_id="smart_workout_device_ready",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device": sensor.label(),
                "owner": self.config_entry.title,
                "vendor": smart_workout_vendor(sensor).title(),
                "status": status.replace("_", " "),
            },
        )

    async def async_step_smart_workout_pairing_help(self, user_input=None):
        """Ask for the minimum device-side action only after pairing failed."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        sensor_id = runtime.resolve_sensor_id(str(getattr(self, "_smart_workout_sensor_id", "")))
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None:
            return await self.async_step_smart_workout_devices()
        vendor = smart_workout_vendor(sensor)
        if user_input is not None:
            action = str(user_input.get("smart_pairing_action") or "later")
            if action == "retry":
                provider = runtime.providers.get("bluetooth")
                archives = getattr(provider, "device_archives", None) if provider else None
                endpoint = sensor.endpoints.get("bluetooth")
                metadata = endpoint.metadata if endpoint is not None else sensor.metadata
                coordinator = archives.coordinator_for_metadata(metadata) if archives is not None else None
                retry = getattr(coordinator, "async_sync_now", None) if coordinator is not None else None
                task = await retry(sensor_id) if retry is not None else None
                # Do not let the OptionsFlow's generic "Success" toast mean only
                # "a retry task was queued". Wait for this one bounded explicit
                # attempt and close successfully only after Garmin negotiation has
                # actually completed without an error. Background automatic syncs
                # remain asynchronous everywhere else.
                if task is not None:
                    await task
                sensor_id = runtime.resolve_sensor_id(sensor_id)
                details = runtime.sensor_detail_values.get(sensor_id, {}) or {}
                error = str(details.get("garmin_last_error") or "none")
                protocol = details.get("garmin_protocol_version")
                if error == "none" and protocol:
                    return self.async_create_entry(
                        title="", data=dict(self.config_entry.options)
                    )
                # The bounded retry failed. Return to the smart-device list so
                # the user sees the device remain action-needed instead of being
                # dropped straight back into the identical pairing-help form.
                return await self.async_step_smart_workout_devices()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="smart_workout_pairing_help",
            data_schema=vol.Schema({
                vol.Required("smart_pairing_action", default="retry"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "retry", "label": "Device is ready for pairing — retry now"},
                            {"value": "later", "label": "I'll do this later"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }),
            description_placeholders={
                "device": sensor.label(), "vendor": vendor.title(), "owner": self.config_entry.title,
            },
        )

    async def async_step_smart_workout_vendor_setup(self, user_input=None):
        """Open vendor instructions without asking the user to guess a model."""
        del user_input
        vendor = setup_vendor(str(getattr(self, "_smart_workout_vendor_id", "")))
        if vendor is None:
            return await self.async_step_smart_workout_devices()
        self._smart_workout_manual_type = DEVICE_TYPE_AUTO
        return await self.async_step_smart_workout_vendor_guide()

    async def async_step_smart_workout_vendor_guide(self, user_input=None):
        """Give vendor/type instructions, then return to bounded discovery."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        vendor = setup_vendor(str(getattr(self, "_smart_workout_vendor_id", "")))
        if vendor is None:
            return await self.async_step_smart_workout_devices()
        if user_input is not None:
            return await self.async_step_smart_workout_devices()
        await self._async_refresh_smart_workout_discovery(runtime)
        matching = []
        for sensor in sorted(runtime.sensors.values(), key=lambda item: item.label().lower()):
            if (
                is_smart_workout_candidate(sensor)
                and smart_workout_vendor(sensor) == vendor.vendor_id
                and smart_workout_archive_compatibility(sensor) is not False
            ):
                matching.append(sensor.label())
            if len(matching) >= 8:
                break
        return self.async_show_form(
            step_id="smart_workout_vendor_guide",
            data_schema=vol.Schema({}),
            description_placeholders={
                "vendor": vendor.label,
                "device_type": "automatically detected",
                "model": "automatically detected",
                "detected_devices": "; ".join(matching) if matching else "—",
            },
        )

    async def async_step_sensor_assignments(self, user_input=None):
        """Choose a physical Local Fitness sensor to reassign after setup."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        choices = [
            {"value": sensor.sensor_id, "label": sensor.label()}
            for sensor in sorted(runtime.sensors.values(), key=lambda item: item.label().lower())
            if runtime.sensor_is_accepted(sensor.sensor_id)
        ]
        if not choices:
            return self.async_abort(reason="no_live_sensors")

        if user_input is not None:
            sensor_id = runtime.resolve_sensor_id(
                str(user_input.get("live_sensor_id") or "")
            )
            if sensor_id not in {item["value"] for item in choices}:
                return self.async_show_form(
                    step_id="sensor_assignments",
                    data_schema=vol.Schema(
                        {
                            vol.Required("live_sensor_id"): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=choices,
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            )
                        }
                    ),
                    errors={"base": "sensor_unavailable"},
                )
            self._assignment_sensor_id = sensor_id
            return await self.async_step_sensor_assignment()

        return self.async_show_form(
            step_id="sensor_assignments",
            data_schema=vol.Schema(
                {
                    vol.Required("live_sensor_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_sensor_assignment(self, user_input=None):
        """Edit the many-to-many profile assignment for one physical sensor."""
        from .live import get_live_runtime

        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        sensor_id = runtime.resolve_sensor_id(
            str(getattr(self, "_assignment_sensor_id", ""))
        )
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None or not runtime.sensor_is_accepted(sensor_id):
            return self.async_abort(reason="sensor_unavailable")

        profile_entries = list(runtime.profile_entries.values())
        profiles = [
            {"value": entry.entry_id, "label": entry.title}
            for entry in profile_entries
        ]
        if not profiles:
            return self.async_abort(reason="no_fitness_profiles")

        current_profiles = [
            entry.entry_id
            for entry in profile_entries
            if sensor_id in runtime.selected_sensor_ids(entry)
        ]

        if user_input is not None:
            selected_profiles = set(user_input.get("fitness_profile_ids") or [])
            changed_entries: list[str] = []
            for entry in profile_entries:
                ids = list(
                    ({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or [])
                )
                resolved_ids = [runtime.resolve_sensor_id(str(item)) for item in ids]
                has_sensor = sensor_id in resolved_ids
                should_have = entry.entry_id in selected_profiles
                if has_sensor == should_have:
                    continue
                # Remove aliases for this canonical physical sensor before adding
                # the current canonical ID. This keeps assignments stable after
                # ANT/BLE identities merge.
                ids = [
                    item
                    for item in ids
                    if runtime.resolve_sensor_id(str(item)) != sensor_id
                ]
                if should_have:
                    ids.append(sensor_id)
                options = dict(entry.options)
                options[CONF_LIVE_SENSOR_IDS] = ids
                # Assignment is a routing relationship, not profile structure.
                # Persist it without invoking the profile reload listener.
                if getattr(getattr(entry, "state", None), "value", None) == "loaded":
                    runtime.suppress_entry_reload_once(entry.entry_id)
                self.hass.config_entries.async_update_entry(entry, options=options)
                changed_entries.append(entry.entry_id)

            runtime.schedule_profile_assignment_refresh(changed_entries)
            runtime.notify_sensor_assignment_changed(sensor_id)

            # Refresh the disabled Workout owner diagnostic so its
            # assigned_profiles attribute reflects this explicit reassignment.
            runtime._notify_values_throttled({(sensor_id, "workout_owner", None)})
            runtime._notify_structure_throttled()
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="sensor_assignment",
            data_schema=vol.Schema(
                {
                    _optional_suggested(
                        "fitness_profile_ids", current_profiles
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=profiles,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"sensor": sensor.label()},
        )

    async def async_step_profile(self, user_input=None):
        """Edit DOB/sex profile data."""
        current = self._current()
        errors = {}

        dob = date.fromisoformat(current[CONF_DATE_OF_BIRTH])

        if user_input is not None:
            try:
                new_dob = date(
                    int(user_input[CONF_BIRTH_YEAR]),
                    int(user_input[CONF_BIRTH_MONTH]),
                    int(user_input[CONF_BIRTH_DAY]),
                )
                if new_dob >= date.today():
                    errors["base"] = "invalid_date"
                else:
                    values = {
                        CONF_DATE_OF_BIRTH: new_dob.isoformat(),
                        CONF_LANGUAGE: _normalize_language(
                            user_input.get(CONF_LANGUAGE)
                        ),
                    }
                    if user_input.get(CONF_SEX):
                        values[CONF_SEX] = _normalize_sex(user_input[CONF_SEX])
                    else:
                        values[CONF_SEX] = None
                    return await self._save_merge(values)
            except (TypeError, ValueError):
                errors["base"] = "invalid_date"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LANGUAGE,
                    default=_normalize_language(
                        current.get(
                            CONF_LANGUAGE,
                            _default_language(self.hass),
                        )
                    ),
                ): _language_selector(),
                vol.Required(
                    CONF_BIRTH_DAY,
                    default=dob.day,
                ): _number(1, 31),
                vol.Required(
                    CONF_BIRTH_MONTH,
                    default=str(dob.month),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[str(i) for i in range(1, 13)],
                        translation_key="birth_month",
                    )
                ),
                vol.Required(
                    CONF_BIRTH_YEAR,
                    default=dob.year,
                ): _number(1900, date.today().year),
                _optional_suggested(
                    CONF_SEX, _normalize_sex(current.get(CONF_SEX))
                ): _sex_selector(),
            }
        )

        return self.async_show_form(
            step_id="profile",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_fitness_inputs(self, user_input=None):
        """Edit manual current weight, shared scale, and other profile inputs."""
        current = self._current()
        errors = {}

        if user_input is not None:
            if not _validate_manual_weight(user_input.get(CONF_WEIGHT)):
                errors[CONF_WEIGHT] = "invalid_number_or_entity"
            if not _validate_weight_scale(self.hass, user_input.get(CONF_WEIGHT_SCALE_ENTITY)):
                errors[CONF_WEIGHT_SCALE_ENTITY] = "invalid_number_or_entity"
            errors.update(
                _validate(
                    self.hass,
                    user_input,
                    {
                        CONF_RESTING_HR: (20, 150, False),
                        CONF_HEIGHT: (50, 260, False),
                        CONF_MAX_HR: (60, 260, False),
                        CONF_VO2MAX: (5, 100, False),
                        CONF_THRESHOLD_HR: (60, 260, False),
                        CONF_THRESHOLD_PACE: (1, 20, False),
                        CONF_THRESHOLD_POWER: (20, 2500, False),
                    },
                    self.config_entry.entry_id,
                )
            )

            if not errors:
                values = {
                    key: user_input.get(key, "")
                    for key in (
                        CONF_WEIGHT,
                        CONF_WEIGHT_SCALE_ENTITY,
                        CONF_RESTING_HR,
                        CONF_HEIGHT,
                        CONF_MAX_HR,
                        CONF_VO2MAX,
                        CONF_THRESHOLD_HR,
                        CONF_THRESHOLD_PACE,
                        CONF_THRESHOLD_POWER,
                    )
                }
                return await self._save_merge(values)

        exact_defaults = exact_profile_defaults(
            self.hass, self.config_entry.entry_id
        )

        def current_text(key, *, required=False):
            value = current.get(key)
            if value not in (None, ""):
                return str(value)
            if required:
                return str(exact_defaults.get(key, ""))
            return ""

        manager = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        runtime_weight = getattr(manager, "current_weight_kg", None) if manager else None
        weight_default = _resolved_weight_default(
            self.hass, runtime_weight if runtime_weight is not None else current.get(CONF_WEIGHT)
        )
        if weight_default is None:
            weight_default = _resolved_weight_default(self.hass, exact_defaults.get(CONF_WEIGHT))

        weight_key = (
            vol.Required(CONF_WEIGHT, default=weight_default)
            if weight_default is not None
            else vol.Required(CONF_WEIGHT)
        )
        scale_current = str(current.get(CONF_WEIGHT_SCALE_ENTITY) or "").strip()
        schema = vol.Schema(
            {
                weight_key: _number(20, 500, step=0.1),
                _optional_suggested(CONF_WEIGHT_SCALE_ENTITY, scale_current): _weight_scale_selector(
                    self.hass, scale_current
                ),
                _optional_suggested(
                    CONF_RESTING_HR, current_text(CONF_RESTING_HR)
                ): _number_or_entity_selector(
                    self.hass, CONF_RESTING_HR, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_HEIGHT, current_text(CONF_HEIGHT)
                ): _number_or_entity_selector(
                    self.hass, CONF_HEIGHT, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_MAX_HR, current_text(CONF_MAX_HR)
                ): _number_or_entity_selector(
                    self.hass, CONF_MAX_HR, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_VO2MAX, current_text(CONF_VO2MAX)
                ): _number_or_entity_selector(
                    self.hass, CONF_VO2MAX, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_THRESHOLD_HR, current_text(CONF_THRESHOLD_HR)
                ): _number_or_entity_selector(
                    self.hass, CONF_THRESHOLD_HR, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_THRESHOLD_PACE, current_text(CONF_THRESHOLD_PACE)
                ): _number_or_entity_selector(
                    self.hass, CONF_THRESHOLD_PACE, self.config_entry.entry_id
                ),
                _optional_suggested(
                    CONF_THRESHOLD_POWER, current_text(CONF_THRESHOLD_POWER)
                ): _number_or_entity_selector(
                    self.hass, CONF_THRESHOLD_POWER, self.config_entry.entry_id
                ),
            }
        )
        return self.async_show_form(
            step_id="fitness_inputs", data_schema=schema, errors=errors
        )

    async def async_step_live_devices(self, user_input=None):
        current = self._current()
        from .live import get_live_runtime
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        if user_input is None and not getattr(self, "_native_live_scan_started", False):
            await runtime.async_begin_setup_discovery()
            self._native_live_scan_started = True
            await asyncio.sleep(2.5)
        selected_native = []
        for raw_id in (current.get(CONF_LIVE_SENSOR_IDS) or []):
            sensor_id = runtime.resolve_sensor_id(str(raw_id))
            if sensor_id not in selected_native:
                selected_native.append(sensor_id)
        choice_map = {
            x.sensor_id: x.label()
            for x in runtime.sensors.values()
            if any(runtime.adapter_enabled(t) for t in x.transports)
        }
        # Never silently drop an assigned sensor just because it has not
        # advertised again since this HA restart.
        for sensor_id in selected_native:
            choice_map.setdefault(sensor_id, f"{sensor_id} — waiting for discovery")
        choices = [
            {"value": sensor_id, "label": label}
            for sensor_id, label in sorted(choice_map.items())
        ]
        generic_choices = live_device_choices(
            self.hass, self.config_entry.entry_id
        )
        if user_input is not None:
            await runtime.async_end_setup_discovery()
            return await self._save_merge(
                {
                    CONF_LIVE_SENSOR_IDS: list(user_input.get(CONF_LIVE_SENSOR_IDS) or []),
                    CONF_LIVE_DEVICE_IDS: list(user_input.get(CONF_LIVE_DEVICE_IDS) or []),
                }
            )
        known_generic = set(_choice_ids(generic_choices))
        selected_generic = [
            x for x in (current.get(CONF_LIVE_DEVICE_IDS) or []) if x in known_generic
        ]
        return self.async_show_form(
            step_id="live_devices",
            data_schema=vol.Schema(
                {
                    _optional_suggested(CONF_LIVE_SENSOR_IDS, selected_native): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=choices, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN
                        )
                    ),
                    _optional_suggested(CONF_LIVE_DEVICE_IDS, selected_generic): _supported_device_multi(
                        generic_choices
                    ),
                }
            ),
        )

    async def async_step_workout_devices(self, user_input=None):
        current = self._current()

        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_WORKOUT_DEVICE_IDS: list(
                        user_input.get(CONF_WORKOUT_DEVICE_IDS) or []
                    ),
                    CONF_DETAILED_STRENGTH_ANALYSIS: bool(
                        user_input.get(CONF_DETAILED_STRENGTH_ANALYSIS, False)
                    ),
                    CONF_WORKOUT_RETENTION_DAYS: int(
                        user_input.get(
                            CONF_WORKOUT_RETENTION_DAYS,
                            DEFAULT_WORKOUT_RETENTION_DAYS,
                        )
                    ),
                    CONF_FIT_FILE_RETENTION_COUNT: int(
                        user_input.get(CONF_FIT_FILE_RETENTION_COUNT, DEFAULT_FIT_FILE_RETENTION_COUNT)
                    ),
                }
            )

        workout_choices = workout_device_choices(
            self.hass, self.config_entry.entry_id
        )
        workout_choice_ids = set(_choice_ids(workout_choices))
        selected_workout_devices = [
            item for item in (current.get(CONF_WORKOUT_DEVICE_IDS) or [])
            if item in workout_choice_ids
        ]
        return self.async_show_form(
            step_id="workout_devices",
            data_schema=vol.Schema(
                {
                    _optional_suggested(
                        CONF_WORKOUT_DEVICE_IDS, selected_workout_devices
                    ): _supported_device_multi(workout_choices),
                    vol.Optional(
                        CONF_DETAILED_STRENGTH_ANALYSIS,
                        default=bool(current.get(CONF_DETAILED_STRENGTH_ANALYSIS, False)),
                    ): bool,
                    vol.Required(
                        CONF_WORKOUT_RETENTION_DAYS,
                        default=int(current.get(CONF_WORKOUT_RETENTION_DAYS, DEFAULT_WORKOUT_RETENTION_DAYS)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=MAX_WORKOUT_RETENTION_DAYS, step=1,
                            unit_of_measurement="d", mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_FIT_FILE_RETENTION_COUNT,
                        default=int(current.get(CONF_FIT_FILE_RETENTION_COUNT, DEFAULT_FIT_FILE_RETENTION_COUNT)),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=500, step=1, mode=selector.NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_history(self, user_input=None):
        """Edit canonical workout-history retention."""
        current = self._current()
        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_WORKOUT_RETENTION_DAYS: int(
                        user_input.get(
                            CONF_WORKOUT_RETENTION_DAYS,
                            DEFAULT_WORKOUT_RETENTION_DAYS,
                        )
                    )
                }
            )
        return self.async_show_form(
            step_id="history",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WORKOUT_RETENTION_DAYS,
                        default=int(
                            current.get(
                                CONF_WORKOUT_RETENTION_DAYS,
                                DEFAULT_WORKOUT_RETENTION_DAYS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=MAX_WORKOUT_RETENTION_DAYS,
                            step=1,
                            unit_of_measurement="d",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )

    async def async_step_sleep_devices(self, user_input=None):
        current = self._current()
        if user_input is not None:
            return await self._save_merge(
                {CONF_SLEEP_DEVICE_IDS: list(user_input.get(CONF_SLEEP_DEVICE_IDS) or [])}
            )
        sleep_choices = sleep_device_choices(
            self.hass, self.config_entry.entry_id
        )
        sleep_choice_ids = set(_choice_ids(sleep_choices))
        selected_sleep_devices = [
            item for item in (current.get(CONF_SLEEP_DEVICE_IDS) or [])
            if item in sleep_choice_ids
        ]
        return self.async_show_form(
            step_id="sleep_devices",
            data_schema=vol.Schema(
                {
                    _optional_suggested(
                        CONF_SLEEP_DEVICE_IDS, selected_sleep_devices
                    ): _supported_device_multi(sleep_choices)
                }
            ),
        )

    async def async_step_ai(self, user_input=None):
        current = self._current()

        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_AI_ENABLED: bool(
                        user_input.get(CONF_AI_ENABLED)
                    ),
                    CONF_AI_ENTITY: (
                        user_input.get(CONF_AI_ENTITY) or ""
                    ),
                    CONF_TRAINING_GOAL: str(user_input.get(CONF_TRAINING_GOAL) or "").strip(),
                    CONF_TRAINING_GOAL_DATE: str(user_input.get(CONF_TRAINING_GOAL_DATE) or "").strip(),
                    CONF_TRAINING_DAYS_PER_WEEK: int(user_input.get(CONF_TRAINING_DAYS_PER_WEEK) or 4),
                }
            )

        configured_ai = (
            (current.get(CONF_AI_ENTITY) or None)
            if CONF_AI_ENTITY in current
            else AI_ENTITY_SYSTEM_DEFAULT
        )
        ai_available = bool(
            self.hass.services.has_service("ai_task", "generate_data")
            or any(
                state.entity_id.startswith(("ai_task.", "conversation."))
                for state in self.hass.states.async_all()
            )
        )

        schema = {
            vol.Optional(
                CONF_AI_ENABLED,
                default=bool(
                    current.get(
                        CONF_AI_ENABLED,
                        ai_available,
                    )
                ),
            ): bool,
            _optional_suggested(
                CONF_AI_ENTITY, configured_ai
            ): _ai_entity(self.hass, configured_ai),
            _optional_suggested(
                CONF_TRAINING_GOAL, current.get(CONF_TRAINING_GOAL)
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            _optional_suggested(
                CONF_TRAINING_GOAL_DATE, current.get(CONF_TRAINING_GOAL_DATE)
            ): selector.DateSelector(),
            vol.Optional(
                CONF_TRAINING_DAYS_PER_WEEK,
                default=int(current.get(CONF_TRAINING_DAYS_PER_WEEK, 4) or 4),
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=7, step=1, mode=selector.NumberSelectorMode.BOX)),
        }

        return self.async_show_form(
            step_id="ai",
            data_schema=vol.Schema(schema),
        )

    async def async_step_feedback(self, user_input=None):
        """Edit coaching/announcement targets."""
        current = self._current()

        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_FEEDBACK_AREA_IDS: list(
                        user_input.get(CONF_FEEDBACK_AREA_IDS) or []
                    ),
                    CONF_FEEDBACK_LIGHT_IDS: list(
                        user_input.get(CONF_FEEDBACK_LIGHT_IDS) or []
                    ),
                    CONF_NOTIFY_ENTITY_IDS: list(
                        user_input.get(CONF_NOTIFY_ENTITY_IDS) or []
                    ),
                    CONF_PERIODIC_LIVE_ANNOUNCEMENTS: bool(
                        user_input.get(CONF_PERIODIC_LIVE_ANNOUNCEMENTS)
                    ),
                    CONF_PERIODIC_LIVE_INTERVAL_MINUTES: int(
                        user_input.get(
                            CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
                            5,
                        )
                    ),
                    CONF_TTS_ENTITY_ID: (
                        user_input.get(CONF_TTS_ENTITY_ID) or ""
                    ),
                    CONF_TTS_MEDIA_PLAYER_IDS: list(
                        user_input.get(CONF_TTS_MEDIA_PLAYER_IDS) or []
                    ),
                }
            )

        schema = {
            _optional_suggested(
                CONF_FEEDBACK_AREA_IDS, list(current.get(CONF_FEEDBACK_AREA_IDS) or [])
            ): _area_multi(),
            _optional_suggested(
                CONF_FEEDBACK_LIGHT_IDS, list(current.get(CONF_FEEDBACK_LIGHT_IDS) or [])
            ): _entity_multi("light"),
            _optional_suggested(
                CONF_NOTIFY_ENTITY_IDS, list(current.get(CONF_NOTIFY_ENTITY_IDS) or [])
            ): _entity_multi("notify"),
        }

        schema[
            vol.Optional(
                CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
                default=bool(
                    current.get(
                        CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
                        False,
                    )
                ),
            )
        ] = bool
        schema[
            vol.Optional(
                CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
                default=int(
                    current.get(
                        CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
                        5,
                    )
                ),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=120,
                step=1,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )

        if CONF_TTS_ENTITY_ID in current:
            # An explicit empty option means the user intentionally removed the
            # previously suggested TTS provider.  Do not silently reselect one.
            current_tts = current.get(CONF_TTS_ENTITY_ID) or None
        else:
            current_tts = _preferred_profile_tts_entity(
                self.hass, current.get(CONF_LANGUAGE) or "en"
            )

        if current_tts:
            schema[
                _optional_suggested(
                    CONF_TTS_ENTITY_ID, current_tts
                )
            ] = _entity_single("tts")
        else:
            schema[vol.Optional(CONF_TTS_ENTITY_ID)] = _entity_single("tts")

        schema[
            _optional_suggested(
                CONF_TTS_MEDIA_PLAYER_IDS, list(current.get(CONF_TTS_MEDIA_PLAYER_IDS) or [])
            )
        ] = _entity_multi("media_player")

        return self.async_show_form(
            step_id="feedback",
            data_schema=vol.Schema(schema),
        )

    async def async_step_tv_dashboard(self, user_input=None):
        """Edit the optional full-screen Fitness TV dashboard."""
        current = self._current()
        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_TV_DASHBOARD_ENABLED: bool(
                        user_input.get(CONF_TV_DASHBOARD_ENABLED, False)
                    ),
                    CONF_TV_MEDIA_PLAYER_ID: str(
                        user_input.get(CONF_TV_MEDIA_PLAYER_ID) or ""
                    ).strip(),
                    CONF_TV_DUCKING_PERCENT: int(
                        user_input.get(
                            CONF_TV_DUCKING_PERCENT,
                            DEFAULT_TV_DUCKING_PERCENT,
                        )
                    ),
                    CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE: bool(
                        user_input.get(
                            CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                            DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                        )
                    ),
                }
            )

        schema = {
            vol.Optional(
                CONF_TV_DASHBOARD_ENABLED,
                default=bool(current.get(CONF_TV_DASHBOARD_ENABLED, False)),
            ): bool,
            vol.Optional(
                CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                default=bool(
                    current.get(
                        CONF_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                        DEFAULT_TV_IGNORE_LIGHTS_WHEN_CAST_ACTIVE,
                    )
                ),
            ): bool,
            _optional_suggested(
                CONF_TV_MEDIA_PLAYER_ID,
                str(current.get(CONF_TV_MEDIA_PLAYER_ID) or ""),
            ): _cast_media_player_single(),
            vol.Optional(
                CONF_TV_DUCKING_PERCENT,
                default=int(
                    current.get(
                        CONF_TV_DUCKING_PERCENT,
                        DEFAULT_TV_DUCKING_PERCENT,
                    )
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
        return self.async_show_form(
            step_id="tv_dashboard",
            data_schema=vol.Schema(schema),
        )

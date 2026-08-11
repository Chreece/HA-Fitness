"""Config flow for Fitness."""

from __future__ import annotations

from datetime import date

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_BIRTH_DAY,
    CONF_BIRTH_MONTH,
    CONF_BIRTH_YEAR,
    CONF_FEEDBACK_AREA_IDS,
    CONF_FEEDBACK_LIGHT_IDS,
    CONF_NOTIFY_ENTITY_IDS,
    CONF_TTS_ENTITY_ID,
    CONF_TTS_MEDIA_PLAYER_IDS,
    CONF_DATE_OF_BIRTH,
    CONF_HEIGHT,
    CONF_LANGUAGE,
    CONF_LIVE_DEVICE_IDS,
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
    CONF_WORKOUT_DEVICE_IDS,
    CONF_SLEEP_DEVICE_IDS,
    DOMAIN,
    SUPPORTED_LANGUAGES,
)
from .providers.entities import is_entity_reference, validate_number_or_entity
from .providers.autofill import exact_profile_defaults
from .providers.capabilities import (
    live_device_choices,
    profile_entity_choices,
    sleep_device_choices,
    workout_device_choices,
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


def _compatible_profile_entities(hass, field: str) -> list[dict[str, str]]:
    """Return only entities the runtime profile parser can safely consume."""
    return profile_entity_choices(hass, field)


def _number_or_entity_selector(hass, field: str):
    """Dropdown compatible entities while still permitting a manual number/ID."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_compatible_profile_entities(hass, field),
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


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


def _ai_entity():
    """Select an AI Task or conversation agent."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=["ai_task", "conversation"],
            multiple=False,
        )
    )


def _first_ai_task_entity(hass):
    """Return the first available AI Task entity for a useful setup default."""
    entities = sorted(
        state.entity_id
        for state in hass.states.async_all()
        if state.entity_id.startswith("ai_task.")
    )
    return entities[0] if entities else None


def _number(min_v, max_v):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v,
            max=max_v,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _validate(hass, user_input, specs):
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
            supported = {item["value"] for item in profile_entity_choices(hass, key)}
            if str(value).strip() not in supported:
                errors[key] = "invalid_number_or_entity"
    return errors


class FitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 11

    def __init__(self):
        self._data = {}
        self._autofill_defaults: dict[str, str] | None = None

    def _profile_autofill(self) -> dict[str, str]:
        if self._autofill_defaults is None:
            self._autofill_defaults = exact_profile_defaults(self.hass)
        return self._autofill_defaults

    async def async_step_user(self, user_input=None):
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
                vol.Optional(CONF_SEX): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            "female",
                            "male",
                            "other",
                            "prefer_not_to_say",
                        ],
                        translation_key="sex",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_required(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _validate(
                self.hass,
                user_input,
                {
                    CONF_WEIGHT: (20, 500, True),
                    CONF_RESTING_HR: (20, 150, True),
                },
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_optional()

        return self.async_show_form(
            step_id="required",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WEIGHT, default=self._profile_autofill().get(CONF_WEIGHT, "")): _number_or_entity_selector(self.hass, CONF_WEIGHT),
                    vol.Required(CONF_RESTING_HR, default=self._profile_autofill().get(CONF_RESTING_HR, "")): _number_or_entity_selector(self.hass, CONF_RESTING_HR),
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
                return await self.async_step_live_devices()

        return self.async_show_form(
            step_id="optional",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HEIGHT): _number_or_entity_selector(self.hass, CONF_HEIGHT),
                    vol.Optional(CONF_MAX_HR): _number_or_entity_selector(self.hass, CONF_MAX_HR),
                    vol.Optional(CONF_VO2MAX, default=self._profile_autofill().get(CONF_VO2MAX, "")): _number_or_entity_selector(self.hass, CONF_VO2MAX),
                    vol.Optional(CONF_THRESHOLD_HR, default=self._profile_autofill().get(CONF_THRESHOLD_HR, "")): _number_or_entity_selector(self.hass, CONF_THRESHOLD_HR),
                    vol.Optional(CONF_THRESHOLD_PACE, default=self._profile_autofill().get(CONF_THRESHOLD_PACE, "")): _number_or_entity_selector(self.hass, CONF_THRESHOLD_PACE),
                    vol.Optional(CONF_THRESHOLD_POWER, default=self._profile_autofill().get(CONF_THRESHOLD_POWER, "")): _number_or_entity_selector(self.hass, CONF_THRESHOLD_POWER),
                }
            ),
            errors=errors,
        )

    async def async_step_live_devices(self, user_input=None):
        if user_input is not None:
            ids = list(user_input.get(CONF_LIVE_DEVICE_IDS) or [])
            if ids:
                self._data[CONF_LIVE_DEVICE_IDS] = ids
            return await self.async_step_workout_devices()

        return self.async_show_form(
            step_id="live_devices",
            data_schema=vol.Schema(
                {vol.Optional(CONF_LIVE_DEVICE_IDS, default=_choice_ids(live_device_choices(self.hass))): _supported_device_multi(live_device_choices(self.hass))}
            ),
        )

    async def async_step_workout_devices(self, user_input=None):
        if user_input is not None:
            ids = list(user_input.get(CONF_WORKOUT_DEVICE_IDS) or [])
            if ids:
                self._data[CONF_WORKOUT_DEVICE_IDS] = ids
            return await self.async_step_sleep_devices()

        return self.async_show_form(
            step_id="workout_devices",
            data_schema=vol.Schema(
                {vol.Optional(CONF_WORKOUT_DEVICE_IDS, default=_choice_ids(workout_device_choices(self.hass))): _supported_device_multi(workout_device_choices(self.hass))}
            ),
        )

    async def async_step_sleep_devices(self, user_input=None):
        if user_input is not None:
            ids = list(user_input.get(CONF_SLEEP_DEVICE_IDS) or [])
            if ids:
                self._data[CONF_SLEEP_DEVICE_IDS] = ids
            return await self.async_step_ai()
        return self.async_show_form(
            step_id="sleep_devices",
            data_schema=vol.Schema(
                {vol.Optional(CONF_SLEEP_DEVICE_IDS, default=_choice_ids(sleep_device_choices(self.hass))): _supported_device_multi(sleep_device_choices(self.hass))}
            ),
        )

    async def async_step_ai(self, user_input=None):
        if user_input is not None:
            self._data.update(
                {k: v for k, v in user_input.items() if v not in (None, "")}
            )
            return await self.async_step_feedback()

        default_ai = _first_ai_task_entity(self.hass)
        ai_available = bool(
            default_ai
            or self.hass.services.has_service("ai_task", "generate_data")
        )

        schema = {
            vol.Optional(CONF_AI_ENABLED, default=ai_available): bool,
        }
        if default_ai:
            schema[
                vol.Optional(
                    CONF_AI_ENTITY,
                    default=default_ai,
                )
            ] = _ai_entity()
        else:
            schema[vol.Optional(CONF_AI_ENTITY)] = _ai_entity()

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

            name = self._data[CONF_PROFILE_NAME]
            await self.async_set_unique_id(
                f"fitness_{name.strip().lower().replace(' ', '_')}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Fitness – {name}",
                data=self._data,
            )

        default_tts = next(
            (
                state.entity_id
                for state in sorted(
                    self.hass.states.async_all(),
                    key=lambda state: state.entity_id,
                )
                if state.entity_id.startswith("tts.")
            ),
            None,
        )

        schema = {
            vol.Optional(
                CONF_FEEDBACK_AREA_IDS,
                default=[],
            ): _area_multi(),
            vol.Optional(
                CONF_FEEDBACK_LIGHT_IDS,
                default=[],
            ): _entity_multi("light"),
            vol.Optional(
                CONF_NOTIFY_ENTITY_IDS,
                default=[],
            ): _entity_multi("notify"),
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
                vol.Optional(
                    CONF_TTS_ENTITY_ID,
                    default=default_tts,
                )
            ] = _entity_single("tts")
        else:
            schema[vol.Optional(CONF_TTS_ENTITY_ID)] = _entity_single("tts")

        schema[
            vol.Optional(
                CONF_TTS_MEDIA_PLAYER_IDS,
                default=[],
            )
        ] = _entity_multi("media_player")

        return self.async_show_form(
            step_id="feedback",
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
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "profile",
                "fitness_inputs",
                "live_devices",
                "workout_devices",
                "sleep_devices",
                "ai",
                "feedback",
            ],
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
                        values[CONF_SEX] = user_input[CONF_SEX]
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
                vol.Optional(
                    CONF_SEX,
                    default=current.get(CONF_SEX),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            "female",
                            "male",
                            "other",
                            "prefer_not_to_say",
                        ],
                        translation_key="sex",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="profile",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_fitness_inputs(self, user_input=None):
        """Edit every direct/entity physiological input."""
        current = self._current()
        errors = {}

        if user_input is not None:
            errors = _validate(
                self.hass,
                user_input,
                {
                    CONF_WEIGHT: (20, 500, True),
                    CONF_RESTING_HR: (20, 150, True),
                    CONF_HEIGHT: (50, 260, False),
                    CONF_MAX_HR: (60, 260, False),
                    CONF_VO2MAX: (5, 100, False),
                    CONF_THRESHOLD_HR: (60, 260, False),
                    CONF_THRESHOLD_PACE: (1, 20, False),
                    CONF_THRESHOLD_POWER: (20, 2500, False),
                },
            )

            if not errors:
                values = {
                    key: user_input.get(key, "")
                    for key in (
                        CONF_WEIGHT,
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

        exact_defaults = exact_profile_defaults(self.hass)

        def current_text(key):
            value = current.get(key)
            if value not in (None, ""):
                return str(value)
            return str(exact_defaults.get(key, ""))

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WEIGHT,
                    default=current_text(CONF_WEIGHT),
                ): _number_or_entity_selector(self.hass, CONF_WEIGHT),
                vol.Required(
                    CONF_RESTING_HR,
                    default=current_text(CONF_RESTING_HR),
                ): _number_or_entity_selector(self.hass, CONF_RESTING_HR),
                vol.Optional(
                    CONF_HEIGHT,
                    default=current_text(CONF_HEIGHT),
                ): _number_or_entity_selector(self.hass, CONF_HEIGHT),
                vol.Optional(
                    CONF_MAX_HR,
                    default=current_text(CONF_MAX_HR),
                ): _number_or_entity_selector(self.hass, CONF_MAX_HR),
                vol.Optional(
                    CONF_VO2MAX,
                    default=current_text(CONF_VO2MAX),
                ): _number_or_entity_selector(self.hass, CONF_VO2MAX),
                vol.Optional(
                    CONF_THRESHOLD_HR,
                    default=current_text(CONF_THRESHOLD_HR),
                ): _number_or_entity_selector(self.hass, CONF_THRESHOLD_HR),
                vol.Optional(
                    CONF_THRESHOLD_PACE,
                    default=current_text(CONF_THRESHOLD_PACE),
                ): _number_or_entity_selector(self.hass, CONF_THRESHOLD_PACE),
                vol.Optional(
                    CONF_THRESHOLD_POWER,
                    default=current_text(CONF_THRESHOLD_POWER),
                ): _number_or_entity_selector(self.hass, CONF_THRESHOLD_POWER),
            }
        )

        return self.async_show_form(
            step_id="fitness_inputs",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_live_devices(self, user_input=None):
        current = self._current()

        if user_input is not None:
            return await self._save_merge(
                {
                    CONF_LIVE_DEVICE_IDS: list(
                        user_input.get(CONF_LIVE_DEVICE_IDS) or []
                    )
                }
            )

        return self.async_show_form(
            step_id="live_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LIVE_DEVICE_IDS,
                        default=[
                            item for item in (current.get(CONF_LIVE_DEVICE_IDS) or [])
                            if item in set(_choice_ids(live_device_choices(self.hass)))
                        ],
                    ): _supported_device_multi(live_device_choices(self.hass))
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
                    )
                }
            )

        return self.async_show_form(
            step_id="workout_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_WORKOUT_DEVICE_IDS,
                        default=[
                            item for item in (current.get(CONF_WORKOUT_DEVICE_IDS) or [])
                            if item in set(_choice_ids(workout_device_choices(self.hass)))
                        ],
                    ): _supported_device_multi(workout_device_choices(self.hass))
                }
            ),
        )

    async def async_step_sleep_devices(self, user_input=None):
        current = self._current()
        if user_input is not None:
            return await self._save_merge(
                {CONF_SLEEP_DEVICE_IDS: list(user_input.get(CONF_SLEEP_DEVICE_IDS) or [])}
            )
        return self.async_show_form(
            step_id="sleep_devices",
            data_schema=vol.Schema(
                {vol.Optional(CONF_SLEEP_DEVICE_IDS, default=[item for item in (current.get(CONF_SLEEP_DEVICE_IDS) or []) if item in set(_choice_ids(sleep_device_choices(self.hass)))]): _supported_device_multi(sleep_device_choices(self.hass))}
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
                }
            )

        default_ai = (
            current.get(CONF_AI_ENTITY)
            or _first_ai_task_entity(self.hass)
        )

        schema = {
            vol.Optional(
                CONF_AI_ENABLED,
                default=bool(
                    current.get(
                        CONF_AI_ENABLED,
                        bool(default_ai),
                    )
                ),
            ): bool,
        }

        if default_ai:
            schema[
                vol.Optional(
                    CONF_AI_ENTITY,
                    default=default_ai,
                )
            ] = _ai_entity()
        else:
            schema[vol.Optional(CONF_AI_ENTITY)] = _ai_entity()

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
            vol.Optional(
                CONF_FEEDBACK_AREA_IDS,
                default=list(
                    current.get(CONF_FEEDBACK_AREA_IDS) or []
                ),
            ): _area_multi(),
            vol.Optional(
                CONF_FEEDBACK_LIGHT_IDS,
                default=list(
                    current.get(CONF_FEEDBACK_LIGHT_IDS) or []
                ),
            ): _entity_multi("light"),
            vol.Optional(
                CONF_NOTIFY_ENTITY_IDS,
                default=list(
                    current.get(CONF_NOTIFY_ENTITY_IDS) or []
                ),
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

        current_tts = (
            current.get(CONF_TTS_ENTITY_ID)
            or next(
                (
                    state.entity_id
                    for state in sorted(
                        self.hass.states.async_all(),
                        key=lambda state: state.entity_id,
                    )
                    if state.entity_id.startswith("tts.")
                ),
                None,
            )
        )

        if current_tts:
            schema[
                vol.Optional(
                    CONF_TTS_ENTITY_ID,
                    default=current_tts,
                )
            ] = _entity_single("tts")
        else:
            schema[vol.Optional(CONF_TTS_ENTITY_ID)] = _entity_single("tts")

        schema[
            vol.Optional(
                CONF_TTS_MEDIA_PLAYER_IDS,
                default=list(
                    current.get(CONF_TTS_MEDIA_PLAYER_IDS) or []
                ),
            )
        ] = _entity_multi("media_player")

        return self.async_show_form(
            step_id="feedback",
            data_schema=vol.Schema(schema),
        )


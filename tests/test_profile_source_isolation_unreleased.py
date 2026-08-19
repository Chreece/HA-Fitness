from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
INIT = (ROOT / "custom_components/fitness/__init__.py").read_text(encoding="utf-8")
CAP = (ROOT / "custom_components/fitness/providers/capabilities.py").read_text(encoding="utf-8")
AUTOFILL = (ROOT / "custom_components/fitness/providers/autofill.py").read_text(encoding="utf-8")


def test_personal_entity_claim_also_claims_its_device():
    assert "def profile_source_owners" in CAP
    assert "First honor explicit physiological entity assignments" in CAP
    assert "Only then claim still-unowned devices" in CAP
    assert "entity_owners.setdefault(entity_id, entry_id)" in CAP
    assert "device_owners.setdefault(str(device_id), entry_id)" in CAP
    assert "def profile_entity_available" in CAP
    assert "def profile_device_available" in CAP


def test_legacy_duplicate_sources_are_masked_for_later_profiles():
    assert "def exclusive_profile_source_overrides" in CAP
    assert 'overrides[field_name] = ""' in CAP
    assert "overrides[field_name] = allowed" in CAP
    assert "The earliest Fitness profile that claimed" in CAP


def test_personal_setup_choices_exclude_sources_owned_by_other_profiles_but_live_is_shareable():
    assert "device_owners = profile_source_owners(hass)" in CAP
    assert "owner is not None and owner != profile_entry_id" in CAP
    assert "entity_owner is not None and entity_owner != profile_entry_id" in CAP
    assert "device_owner is not None and device_owner != profile_entry_id" in CAP
    assert "profile_entity_choices(hass, field, profile_entry_id)" in FLOW
    assert "profile_entity_choices(hass, field, profile_entry_id)" in AUTOFILL
    device_fields = CAP[CAP.index("_PROFILE_DEVICE_FIELDS = ("):CAP.index("def _profile_entries") ]
    assert "CONF_WORKOUT_DEVICE_IDS" in device_fields
    assert "CONF_SLEEP_DEVICE_IDS" in device_fields
    assert "CONF_LIVE_DEVICE_IDS" not in device_fields
    live = CAP[CAP.index("def live_device_choices("):CAP.index("def workout_device_choices(")]
    assert "Live inputs are intentionally cross-profile" in live
    assert "device_owners" not in live


def test_optional_setup_inputs_are_clearable_suggestions_not_forced_defaults():
    start = FLOW.index("async def async_step_optional")
    end = FLOW.index("async def _async_next_live_setup_step", start)
    block = FLOW[start:end]
    assert "autofill = self._profile_autofill()" in block
    assert "_optional_suggested(CONF_VO2MAX, autofill.get(CONF_VO2MAX))" in block
    assert "_optional_suggested(CONF_THRESHOLD_HR, autofill.get(CONF_THRESHOLD_HR))" in block
    assert "default=self._profile_autofill().get(CONF_VO2MAX" not in block


def test_options_use_suggestions_instead_of_defaults_for_clearable_sources():
    assert "def _optional_suggested" in FLOW
    assert 'description={"suggested_value": value}' in FLOW
    fitness_start = FLOW.index("async def async_step_fitness_inputs")
    fitness_end = FLOW.index("async def async_step_live_devices", fitness_start)
    block = FLOW[fitness_start:fitness_end]
    assert "_optional_suggested(\n                    CONF_VO2MAX" in block
    assert "self.config_entry.entry_id" in block
    assert 'return ""' in block


def test_workout_and_sleep_device_preselection_is_clearable_and_unclaimed_only():
    assert "workout_choices = workout_device_choices(self.hass)" in FLOW
    assert "CONF_WORKOUT_DEVICE_IDS, _choice_ids(workout_choices)" in FLOW
    assert "sleep_choices = sleep_device_choices(self.hass)" in FLOW
    assert "CONF_SLEEP_DEVICE_IDS, _choice_ids(sleep_choices)" in FLOW
    assert "workout_device_choices(\n            self.hass, self.config_entry.entry_id" in FLOW
    assert "sleep_device_choices(\n            self.hass, self.config_entry.entry_id" in FLOW


def test_v14_migration_and_runtime_setup_enforce_source_isolation():
    assert "VERSION = 14" in FLOW
    assert "if config_entry.version > 14:" in INIT
    assert "exclusive_profile_source_overrides" in INIT
    assert "source_overrides = exclusive_profile_source_overrides(hass, entry)" in INIT


def test_weight_scale_is_shareable_without_weakening_other_personal_sources():
    fields = CAP[CAP.index("_PROFILE_ENTITY_FIELDS = ("):CAP.index("_PROFILE_DEVICE_FIELDS = (")]
    assert "CONF_WEIGHT," not in fields
    assert "CONF_RESTING_HR" in fields
    assert "def weight_scale_entity_choices" in CAP
    assert "enforce_ownership=False" in CAP
    assert "CONF_WEIGHT_SCALE_ENTITY" in FLOW

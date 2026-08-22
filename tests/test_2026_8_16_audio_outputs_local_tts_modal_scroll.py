from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_audio_output_is_persisted_per_fitness_profile_and_exposed_to_both_settings_surfaces():
    assert 'DEFAULT_AUDIO_OUTPUT_ID = "__fitness_browser__"' in TV
    assert 'async def async_audio_output_id(self, profile_entry_id: str)' in TV
    assert '"audio_output_id": self._sanitize_audio_output_id(profile.get("audio_output_id"))' in TV
    assert 'vol.Optional("audio_output_id"): str' in TV
    assert '"audio_outputs": (' in DASH and '_fitness_audio_outputs(hass, registry)' in DASH and 'local_ha_hardware_allowed' in DASH
    assert JS.count('id="cfg-audio-output"') >= 2
    assert JS.count('audio_output_id:') >= 2


def test_every_state_backed_compatible_media_player_is_listed_and_ma_outputs_are_preferred():
    helper = DASH[DASH.index("def _fitness_audio_outputs("):DASH.index("\n\ndef _tv_cast_targets")]
    assert 'for state in hass.states.async_all("media_player"):' in helper
    assert 'registry_entry = registry.async_get(state.entity_id)' in helper
    assert 'MediaPlayerEntityFeature.PLAY_MEDIA' in helper
    assert 'platform in {"music_assistant", "mass"}' in helper
    assert 'state.attributes.get("mass_player_type")' in helper
    assert 'not bool(item["music_assistant"])' in helper


def test_ma_managed_speaker_uses_standard_ha_media_player_path_and_adapter_resolution():
    play = TV[TV.index("    async def _async_play_on_ha_output("):TV.index("    async def _async_control_ha_output(")]
    assert 'platform in {"music_assistant", "mass"}' in play
    assert 'state.attributes.get("mass_player_type")' in play
    assert 'decode_music_assistant_media_id(media_content_id)' in play
    assert 'await self.async_resolve_fitness_media(' in play
    assert 'FITNESS_RADIO_PREFIX, FITNESS_URL_PREFIX, FITNESS_YTDLP_PREFIX' in play
    assert 'FITNESS_YOUTUBE_PREFIX, FITNESS_SOUNDCLOUD_PREFIX' in play
    assert '"media_player",\n                "play_media"' in play
    assert 'play_payload["enqueue"] = "replace"' in play
    assert 'music_assistant.play_media' not in play



def test_shared_ha_speaker_output_is_owned_by_only_one_active_fitness_profile():
    assert 'def _ha_output_busy_owner(' in TV
    assert 'return {"sent": False, "reason": "audio_output_in_use"}' in TV
    assert 'owner and not str(owner).startswith("ha:") and owner not in clients' in TV
    assert 'self._audio_owner.get(profile_entry_id) == f"ha:{previous_audio_output}"' in TV
    assert 'if owner.startswith("ha:"):' in TV
    assert 'target={"entity_id": output}, blocking=True' in TV

def test_configured_cast_tv_is_not_offered_as_a_second_generic_audio_output():
    assert JS.count('filter((output) => String(output?.entity_id || "") !== preferred)') >= 2
    assert JS.count("l.audio_output_browser") >= 2


def test_local_tts_auto_selection_is_profile_language_aware_and_never_picks_random_cloud_provider():
    preferred = MANAGER[MANAGER.index("    def _preferred_tts_entity("):MANAGER.index("    def _active_tts_entity(")]
    assert 'desired = self._ai_language().lower()' in preferred
    assert 'if "piper" in label:' in preferred
    assert 'elif platform == "wyoming":' in preferred
    assert 'never silently switches an unconfigured profile to a cloud TTS service' in preferred
    active = MANAGER[MANAGER.index("    def _active_tts_entity("):MANAGER.index("    def _tts_language_for_entity(")]
    assert 'if CONF_TTS_ENTITY_ID in self.config and not configured:' in active

    flow = FLOW[FLOW.index("def _preferred_profile_tts_entity("):FLOW.index("class FitnessConfigFlow")]
    assert 'if "piper" in label:' in flow
    assert 'elif platform == "wyoming":' in flow
    assert 'supported_languages' in flow


def test_tts_follows_only_the_profiles_actively_playing_output_then_falls_back_to_tts_targets():
    speak = MANAGER[MANAGER.index("    async def _async_speak("):MANAGER.index("    async def _async_notify(")]
    assert 'profile_media_playing = bool(' in speak
    assert 'output_state.state == "playing"' in speak
    assert 'profile_media_playing = profile_media_playing and (' in speak
    assert '[profile_audio_output]' in speak
    assert 'media_players = self._feedback_media_player_ids()' in speak
    assert 'await self.hass.services.async_call(\n                        "tts",\n                        "speak"' in speak


def test_all_tv_modals_keep_outer_shell_fixed_and_forward_wheel_to_internal_scroll_body():
    assert '.modal-backdrop{position:fixed' in JS
    assert 'overflow:hidden;overscroll-behavior:none' in JS
    assert '.fitness-modal-scroll-region{' in JS
    assert 'flex:1 1 auto!important' in JS
    assert 'overflow-y:auto!important' in JS
    assert '.remote-gateway-modal>.remote-gateway-body' in JS
    assert 'scrollRegion.scrollTop = before + delta;' in JS
    assert '{passive:false}' in JS
    assert JS.count('_fitnessNormalizeModalScroll(modalCard, {disabled:backendFlowModal || cardPickerPreview})') >= 2
    assert JS.count('_fitnessWireModalScroll(modalCard, scrollBody);') >= 2


def test_dashboard_modal_scroll_selector_is_in_scope_for_wheel_forwarding():
    modal = JS[JS.index("  _showModal(content) {"):JS.index("  async _openMediaBrowser()")]
    backend_at = modal.index('const backendFlowModal = Boolean(')
    preview_at = modal.index('const cardPickerPreview = Boolean(')
    normalize_at = modal.index('const scrollBody = _fitnessNormalizeModalScroll(')
    wire_at = modal.index('_fitnessWireModalScroll(modalCard, scrollBody);')
    assert backend_at < preview_at < normalize_at < wire_at
    assert '{disabled:backendFlowModal || cardPickerPreview}' in modal

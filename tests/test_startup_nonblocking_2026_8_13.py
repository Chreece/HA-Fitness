from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = (ROOT / "custom_components/fitness/manager.py").read_text()
S = (ROOT / "custom_components/fitness/sensor.py").read_text()
I = (ROOT / "custom_components/fitness/__init__.py").read_text()

def test_profile_setup_defers_provider_discovery_until_ha_started():
    setup = M[M.index("    async def async_setup(self):"):M.index("    async def async_shutdown(self):")]
    pre, post = setup.split("    async def _async_post_start_setup", 1)
    assert "discover_external_workouts" not in pre
    assert "discover_latest_sleep" not in pre
    assert "discover_candidates" not in pre
    assert "EVENT_HOMEASSISTANT_STARTED" in pre
    assert "discover_latest_sleep" in post
    assert "discover_candidates" in post

def test_entity_properties_do_not_build_heavy_evaluation_during_bootstrap():
    assert 'if not self.manager.post_start_ready:' in S
    assert 'm in {"readiness", "estimated_recovery_time"} and not self.manager.post_start_ready' in S

def test_latest_workout_is_cached():
    section = M[M.index("    def latest_workout(self)"):M.index("    @staticmethod", M.index("    def latest_workout(self)"))]
    assert "_latest_workout_cache_ready" in section
    assert "return self._latest_workout_cache" in section

def test_global_setup_does_not_initialize_live_runtime():
    section = I[I.index("async def async_setup("):I.index("def _default_profile_language")]
    assert "get_live_runtime" not in section
    assert "async_initialize" not in section

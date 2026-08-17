"""Regression contracts for bounded background, storage and proxy work."""

from pathlib import Path


ROOT = Path(__file__).parents[1] / "custom_components" / "fitness"
MANAGER = (ROOT / "manager.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "live" / "runtime.py").read_text(encoding="utf-8")
REMOTE = (ROOT / "remote_gateway.py").read_text(encoding="utf-8")
CYCPLUS = (ROOT / "live" / "cycplus_m1.py").read_text(encoding="utf-8")
TV = (ROOT / "tv_dashboard.py").read_text(encoding="utf-8")
MUSIC = (ROOT / "music" / "registry.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")


def test_remote_ant_assignment_is_deduplicated_per_gateway() -> None:
    assert "self._ant_assignment_tasks" in REMOTE
    assert "self._ant_assignment_pending" in REMOTE
    assert "schedule_ant_assignments(" in REMOTE
    packet_handler = REMOTE[REMOTE.index("async def websocket_remote_gateway_ant_packets") :]
    assert "hass.async_create_background_task(" not in packet_handler.split(
        "async def websocket_remote_gateway_status", 1
    )[0]


def test_profile_writes_and_live_topology_writes_are_serialized() -> None:
    assert "self._save_lock = asyncio.Lock()" in MANAGER
    assert "def _schedule_save(self)" in MANAGER
    assert "async with self._save_lock" in MANAGER
    assert "self._save_lock = asyncio.Lock()" in RUNTIME
    assert "async def _async_flush_scheduled_saves" in RUNTIME


def test_runtime_shutdown_owns_monitors_and_bounds_provider_teardown() -> None:
    shutdown = RUNTIME[RUNTIME.index("    async def async_shutdown(self)") :]
    assert "self._presence_task" in shutdown
    assert "self._presence_unsubs.clear()" in shutdown
    assert "self._discovery_tasks.clear()" in shutdown
    assert "self._control_tasks.clear()" in shutdown
    assert "self._sensor_device_refresh_handles.clear()" in shutdown
    assert "asyncio.timeout(RUNTIME_OPERATION_TIMEOUT)" in shutdown
    assert "await self.async_shutdown()" in RUNTIME[
        RUNTIME.index("    async def async_unregister_hub") :
        RUNTIME.index("    def ensure_transport_subentry")
    ]


def test_live_samples_and_cycplus_notifications_have_hard_caps() -> None:
    assert "MAX_LIVE_SESSION_SAMPLES = 21_600" in MANAGER
    assert "self.samples = self.samples[::2]" in MANAGER
    assert "PROTOCOL_NOTIFICATION_QUEUE_LIMIT = 128" in CYCPLUS
    assert "maxsize=PROTOCOL_NOTIFICATION_QUEUE_LIMIT" in CYCPLUS
    assert "MAX_RUNTIME_LIVE_SENSORS = 4_096" in RUNTIME
    assert "MAX_PERSISTED_LIVE_SENSORS = 2_048" in RUNTIME


def test_tv_network_bridges_and_persisted_state_are_bounded() -> None:
    assert "SENDSPIN_MAX_MESSAGE_BYTES = 2 * 1024 * 1024" in TV
    assert "max_msg_size=SENDSPIN_MAX_MESSAGE_BYTES" in TV
    assert "ClientTimeout(" in TV
    assert "TV_PROXY_TOKEN_LIMIT = 256" in TV
    assert "def _sanitize_profile" in TV
    assert "self._store_lock = asyncio.Lock()" in TV


def test_optional_provider_calls_have_deadlines() -> None:
    assert "async with asyncio.timeout(30.0)" in MUSIC
    assert (ROOT / "resource_safety.py").is_file()
    safety = (ROOT / "resource_safety.py").read_text(encoding="utf-8")
    assert "async with asyncio.timeout" in safety


def test_route_parsing_and_rendering_are_bounded() -> None:
    assert "FITNESS_ROUTE_MAX_INPUT_CHARS = 250000" in FRONTEND
    assert "FITNESS_ROUTE_MAX_EXTRACTED_POINTS = 20000" in FRONTEND
    assert "FITNESS_ROUTE_MAX_RENDER_POINTS = 5000" in FRONTEND
    assert "depth > FITNESS_ROUTE_MAX_DEPTH" in FRONTEND
    assert "this._renderPoints(this._extractPoints(value))" in FRONTEND

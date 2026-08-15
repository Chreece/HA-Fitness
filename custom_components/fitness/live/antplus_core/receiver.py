"""Continuous ANT+ scan-mode receiver."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any

from openant.devices import ANTPLUS_NETWORK_KEY
from openant.easy.channel import Channel
from openant.easy.node import Node

from .const import (
    ANTPLUS_NETWORK_NUMBER,
    ANTPLUS_RF_FREQUENCY,
    DEVICE_TYPE_FITNESS_EQUIPMENT,
    DEVICE_TYPE_HEART_RATE,
    DEVICE_TYPE_POWER,
    DEVICE_TYPE_CONTROLS,
    DEVICE_TYPE_LEV,
    DEVICE_TYPE_ENVIRONMENT,
    DEVICE_TYPE_SHIFTING,
    DEVICE_TYPE_TIRE_PRESSURE,
    DEVICE_TYPE_DROPPER,
    DEVICE_TYPE_BIKE_SPEED_CADENCE,
    DEVICE_TYPE_BIKE_CADENCE,
    DEVICE_TYPE_BIKE_SPEED,
    DEVICE_TYPE_STRIDE_SPEED,
    DEVICE_TYPE_CORE_TEMP,
    DEVICE_TYPE_NAMES,
)
from .decoder import decode_packet
from .capabilities import capability_signature, record_fe_command_status, record_observed_page
from .diagnostics import AntPlusDiagnostics
from .models import AntDevice
from ..vendor_registry import catalog_manufacturer_name

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LOCAL_USB_IDS = {("0FCF", "1008"), ("0FCF", "1009")}

# Wildcard ANT scan mode can occasionally yield malformed/transient extended
# packets. Do not create a persistent HA device/profile from a single packet.
#
# Profiles that Fitness actually decodes semantically are already constrained by
# a standardized ANT device type and validated extended channel identity, so they
# can use a shorter confirmation sequence. This matters especially for low-rate
# profiles such as Environment (commonly 0.5 Hz): a fixed five-packet rule makes
# a valid sensor feel much slower than a 4 Hz HR/BSC sensor. Unknown/raw-only
# profiles deliberately retain the more conservative five-packet guard.
DISCOVERY_CONFIRM_PACKETS = 5
SEMANTIC_DISCOVERY_CONFIRM_PACKETS = 3
SEMANTIC_DISCOVERY_PROFILE_TYPES = frozenset({
    DEVICE_TYPE_POWER,
    DEVICE_TYPE_CONTROLS,
    DEVICE_TYPE_FITNESS_EQUIPMENT,
    DEVICE_TYPE_LEV,
    DEVICE_TYPE_ENVIRONMENT,
    DEVICE_TYPE_SHIFTING,
    DEVICE_TYPE_TIRE_PRESSURE,
    DEVICE_TYPE_DROPPER,
    DEVICE_TYPE_HEART_RATE,
    DEVICE_TYPE_BIKE_SPEED_CADENCE,
    DEVICE_TYPE_BIKE_CADENCE,
    DEVICE_TYPE_BIKE_SPEED,
    DEVICE_TYPE_STRIDE_SPEED,
    DEVICE_TYPE_CORE_TEMP,
})
DISCOVERY_CONFIRM_WINDOW_SECONDS = 10.0
DISCOVERY_CANDIDATE_TTL_SECONDS = 30.0
MAX_DISCOVERY_CANDIDATES = 256
MAX_CONFIRMED_DEVICES = 256
MAX_PROFILES_PER_DEVICE = 16
MAX_METRICS_PER_DEVICE = 96

# Accepted physical sensors remain visible even while no profile is training.
# Decode at most two packets per second per ANT profile while idle so raw HA
# entities (power/cadence/speed/distance/etc.) stay current without radio-rate
# decoder or callback load. Active/recovery sessions bypass this sampler.
IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS = 0.5
ANT_LAST_SEEN_CALLBACK_INTERVAL_SECONDS = 60.0


# Identity pages are profile-specific. Never infer an identity layout merely
# because a device type is recognized. Power, FE and SDM use ANT common pages
# 80/81; HRM uses profile pages 2/3; BSC speed/cadence profiles use their own
# pages 2/3 (manufacturer+serial and version/model respectively). This explicit
# policy prevents raw telemetry pages from being misread as device identity.
COMMON_IDENTITY_PAGE_PROFILES = frozenset({
    DEVICE_TYPE_POWER,
    DEVICE_TYPE_FITNESS_EQUIPMENT,
    DEVICE_TYPE_STRIDE_SPEED,
})
BSC_IDENTITY_PAGE_PROFILES = frozenset({
    DEVICE_TYPE_BIKE_SPEED_CADENCE,
    DEVICE_TYPE_BIKE_CADENCE,
    DEVICE_TYPE_BIKE_SPEED,
})
IDENTITY_CONFIRM_OBSERVATIONS = 2

DeviceCallback = Callable[[AntDevice], None]
MetricCallback = Callable[[AntDevice, str], None]
StateCallback = Callable[[], None]
PacketCallback = Callable[[AntDevice, int, int, bytes, str], None]


def _discovery_confirmation_packets(device_type: int) -> int:
    """Return the RF confirmation count for one ANT profile."""
    return (
        SEMANTIC_DISCOVERY_CONFIRM_PACKETS
        if int(device_type) in SEMANTIC_DISCOVERY_PROFILE_TYPES
        else DISCOVERY_CONFIRM_PACKETS
    )


def _is_identity_page(device_type: int, page: int) -> bool:
    """Return whether ``page`` has a proven identity layout for this profile."""
    device_type = int(device_type)
    page = int(page) & 0x7F
    if device_type in COMMON_IDENTITY_PAGE_PROFILES:
        return page in (0x50, 0x51)
    if device_type == DEVICE_TYPE_HEART_RATE:
        return page in (2, 3)
    if device_type in BSC_IDENTITY_PAGE_PROFILES:
        return page in (2, 3)
    return False


class AntPlusReceiver:
    """Own the ANT USB stick and receive all broadcasts on one scan channel."""

    def __init__(self) -> None:
        self.devices: dict[int, AntDevice] = {}
        self._node: Node | None = None
        self._channel: Channel | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._control_lock = threading.RLock()
        self._started_event = threading.Event()
        self._device_callbacks: list[DeviceCallback] = []
        self._metric_callbacks: list[MetricCallback] = []
        self._state_callbacks: list[StateCallback] = []
        self._packet_callbacks: list[PacketCallback] = []
        # MainThread may toggle acceptance while ANT workers are busy. Use
        # copy-on-write immutable snapshots so HA never waits on the packet lock.
        self._telemetry_enabled_devices: frozenset[int] = frozenset()
        # Accepted/configured devices are a separate concept from profile live
        # telemetry. Accepted sensors may still publish their own raw physical HA
        # entities while idle, but at a heavily sampled rate. Copy-on-write keeps
        # MainThread acceptance/live-gate updates lock-free for radio workers.
        self._accepted_devices: frozenset[int] = frozenset()
        # Lock-free snapshot of already-confirmed profiles. New profiles always
        # bypass the idle sampler so discovery can never be starved.
        self._known_profiles_snapshot: dict[int, frozenset[int]] = {}
        # Worker-thread idle sampling state. Local ANT and the remote coalescer may
        # race benignly here; at worst one extra packet is admitted in a window.
        # No Home Assistant registry/state operation is performed from this map.
        self._idle_packet_last_admitted: dict[tuple[int, int, int], float] = {}
        # Metric values may remain identical for minutes (for example a steady
        # heart rate).  Keep a separate worker-side heartbeat so the physical
        # sensor Last seen entity can still advance once per minute without
        # turning every RF packet into a Home Assistant callback.
        self._last_presence_callback_monotonic: dict[int, float] = {}
        self._forget_requested: frozenset[int] = frozenset()
        # Identity is structural state. Never mutate it from one radio packet.
        # Candidate tuples must repeat before they are committed.
        self._identity_candidates: dict[
            tuple[int, int, int], tuple[tuple[tuple[str, object], ...], int]
        ] = {}
        self.diagnostics = AntPlusDiagnostics()

        # Unconfirmed RF discoveries. A tuple is promoted only after repeated
        # observations, preventing one malformed wildcard-scan packet from
        # permanently creating a Home Assistant device.
        self._discovery_candidates: dict[
            tuple[int, int, int],
            dict[str, Any],
        ] = {}

        self.error: str | None = None
        self._state = "stopped"

        # Global HA ANT+ capture state.
        #
        # True:
        #   - local ANT USB reception is enabled
        #   - remote ANT+ packets are accepted
        #
        # False:
        #   - local ANT USB reception is stopped
        #   - remote ANT+ packets are discarded
        self._capture_enabled = True

    @property
    def running(self) -> bool:
        """Return whether the local ANT USB receiver is running."""
        return self._state == "running"

    @property
    def capture_enabled(self) -> bool:
        """Return the global HA ANT+ capture state."""
        return self._capture_enabled

    @property
    def state(self) -> str:
        return self._state

    def forget_device(self, device_id: int) -> None:
        """Request receiver-side forget without blocking Home Assistant."""
        device_id = int(device_id)
        self._telemetry_enabled_devices = (
            self._telemetry_enabled_devices - {device_id}
        )
        self._accepted_devices = self._accepted_devices - {device_id}
        for key in tuple(self._idle_packet_last_admitted):
            if key[0] == device_id:
                self._idle_packet_last_admitted.pop(key, None)
        self._last_presence_callback_monotonic.pop(device_id, None)
        known = dict(self._known_profiles_snapshot)
        known.pop(device_id, None)
        self._known_profiles_snapshot = known
        self._forget_requested = self._forget_requested | {device_id}

    def set_device_telemetry_enabled(
        self, device_id: int, enabled: bool
    ) -> None:
        """Publish one lock-free live-telemetry snapshot for ANT workers."""
        device_id = int(device_id)
        current = self._telemetry_enabled_devices
        self._telemetry_enabled_devices = (
            current | {device_id} if enabled else current - {device_id}
        )

    def set_device_accepted(self, device_id: int, accepted: bool) -> None:
        """Publish whether one ANT identity belongs to a configured sensor."""
        device_id = int(device_id)
        current = self._accepted_devices
        self._accepted_devices = (
            current | {device_id} if accepted else current - {device_id}
        )
        if not accepted:
            for key in tuple(self._idle_packet_last_admitted):
                if key[0] == device_id:
                    self._idle_packet_last_admitted.pop(key, None)

    def fast_ignore_idle_packet(
        self, device_id: int, device_type: int, page: int = -1
    ) -> bool:
        """Rate-limit known accepted ANT pages while no live session needs them.

        Raw physical sensor entities must remain useful while Fitness is idle, so an
        accepted sensor is no longer dropped completely. Instead, each known ANT
        page is admitted at most twice per second. Page-aware sampling is important
        for profiles such as stride speed/distance where speed/distance and cadence
        are carried on different rotating pages. New/unaccepted profiles always pass
        for discovery and active/recovery telemetry is never sampled.

        Call this exactly once per packet, from ``process_packet``. It intentionally
        performs no HA work and only updates a tiny worker-side monotonic timestamp.
        """
        device_id = int(device_id)
        device_type = int(device_type)
        page = int(page) & 0x7F if int(page) >= 0 else -1
        if (
            device_id not in self._accepted_devices
            or device_id in self._telemetry_enabled_devices
            or device_type not in self._known_profiles_snapshot.get(device_id, frozenset())
        ):
            return False
        now = time.monotonic()
        key = (device_id, device_type, page)
        previous = self._idle_packet_last_admitted.get(key)
        if (
            previous is not None
            and now - previous < IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS
        ):
            return True
        self._idle_packet_last_admitted[key] = now
        return False

    def add_device_callback(self, callback: DeviceCallback) -> Callable[[], None]:
        self._device_callbacks.append(callback)
        return lambda: self._remove_callback(self._device_callbacks, callback)

    def add_metric_callback(self, callback: MetricCallback) -> Callable[[], None]:
        self._metric_callbacks.append(callback)
        return lambda: self._remove_callback(self._metric_callbacks, callback)

    def add_state_callback(self, callback: StateCallback) -> Callable[[], None]:
        self._state_callbacks.append(callback)
        return lambda: self._remove_callback(self._state_callbacks, callback)

    def add_packet_callback(self, callback: PacketCallback) -> Callable[[], None]:
        """Register for confirmed raw ANT+ packets after identity validation."""
        self._packet_callbacks.append(callback)
        return lambda: self._remove_callback(self._packet_callbacks, callback)

    @staticmethod
    def _remove_callback(callbacks: list, callback: Callable) -> None:
        try:
            callbacks.remove(callback)
        except ValueError:
            pass

    def _set_state(self, state: str, error: str | None = None) -> None:
        self._state = state
        if error is not None:
            self.error = error
        elif state in ("starting", "running", "remote"):
            self.error = None

        if state in ("running", "remote", "error", "stopped"):
            self._started_event.set()

        for callback in tuple(self._state_callbacks):
            try:
                callback()
            except Exception:
                _LOGGER.debug("ANT+ state callback failed", exc_info=True)

    def _local_usb_present(self) -> bool:
        """Return whether a supported ANT USB adapter is attached locally."""
        root = Path("/sys/bus/usb/devices")
        if not root.exists():
            return False
        for device_path in root.glob("*"):
            try:
                vid = (device_path / "idVendor").read_text().strip().upper()
                pid = (device_path / "idProduct").read_text().strip().upper()
            except (OSError, UnicodeError):
                continue
            if (vid, pid) in SUPPORTED_LOCAL_USB_IDS:
                return True
        return False

    def enable_capture(self) -> None:
        """Enable capture from all ANT+ sources."""
        with self._control_lock:
            changed = not self._capture_enabled
            self._capture_enabled = True

        if changed:
            for callback in tuple(self._state_callbacks):
                try:
                    callback()
                except Exception:
                    _LOGGER.debug(
                        "ANT+ state callback failed",
                        exc_info=True,
                    )

        # Start local OpenANT only if local ANT USB hardware exists.
        if self._local_usb_present():
            self.start(wait=False)
        else:
            self._set_state("remote")

    def disable_capture(self) -> None:
        """Disable capture from all ANT+ sources."""
        with self._control_lock:
            changed = self._capture_enabled
            self._capture_enabled = False
        # Stop the local USB receiver.
        self.stop()

        if changed:
            for callback in tuple(self._state_callbacks):
                try:
                    callback()
                except Exception:
                    _LOGGER.debug(
                        "ANT+ state callback failed",
                        exc_info=True,
                    )

    def start(self, wait: bool = True) -> None:
        """Start the optional local ANT USB receiver."""
        # Missing local USB is normal in a remote-gateway setup.
        if not self._local_usb_present():
            self._set_state("remote")
            return
        with self._control_lock:
            if not self._capture_enabled:
                return

            if self._state in ("starting", "running"):
                return

            thread = self._thread
            if thread and thread.is_alive():
                _LOGGER.warning("ANT+ receiver thread is still alive; refusing duplicate start")
                return

            self._started_event.clear()
            self._set_state("starting")
            self._thread = threading.Thread(
                target=self._run,
                name="antplus-receiver",
                daemon=True,
            )
            self._thread.start()

        if wait:
            # Give interactive callers a deterministic result.
            self._started_event.wait(timeout=5)

    def stop(self) -> None:
        """Stop capture and wait for the receiver thread to terminate."""
        with self._control_lock:
            if self._state == "stopped":
                return

            self._set_state("stopping")
            node = self._node
            if node is not None:
                try:
                    node.stop()
                except Exception:
                    _LOGGER.debug("Error stopping ANT+ node", exc_info=True)

            thread = self._thread

        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=10)

        with self._control_lock:
            if thread and thread.is_alive():
                self._set_state(
                    "error",
                    "ANT+ receiver did not stop within 10 seconds",
                )
                return

            self._thread = None
            self._node = None
            self._channel = None
            self._set_state("stopped")



    def snapshot(self) -> dict[int, AntDevice]:
        with self._lock:
            return dict(self.devices)

    def _run(self) -> None:
        try:
            node = Node()
            self._node = node
            node.set_network_key(ANTPLUS_NETWORK_NUMBER, ANTPLUS_NETWORK_KEY)

            channel = node.new_channel(
                Channel.Type.BIDIRECTIONAL_RECEIVE,
                ANTPLUS_NETWORK_NUMBER,
                0x01,
            )
            self._channel = channel
            channel.on_broadcast_data = self._on_data
            channel.on_burst_data = self._on_data
            channel.on_acknowledge = self._on_data
            channel.set_id(0, 0, 0)
            channel.enable_extended_messages(1)
            channel.set_rf_freq(ANTPLUS_RF_FREQUENCY)

            _LOGGER.info("Opening ANT+ continuous RX scan mode")
            channel.open_rx_scan_mode()

            self._set_state("running")
            node.start()

        except Exception as err:
            _LOGGER.exception("ANT+ receiver stopped with an error")
            self._set_state("error", str(err))

        finally:
            node = self._node
            if node is not None:
                try:
                    node.stop()
                except Exception:
                    pass

            self._node = None
            self._channel = None

            # If stop() initiated shutdown, let stop() publish "stopped".
            if self._state not in ("stopping", "error"):
                self._set_state("stopped")

    def _on_data(self, data: Any) -> None:
        """Receive one packet from the local ANT USB adapter."""
        if len(data) < 13:
            return

        device_id = int(data[9]) | (int(data[10]) << 8)
        device_type = int(data[11])
        payload = bytes(data[:8])
        transmission_type = int(data[12])

        self.process_packet(
            device_id=device_id,
            device_type=device_type,
            transmission_type=transmission_type,
            payload=payload,
            source="local",
        )

    def _expire_discovery_candidates(self, now_ts: float) -> None:
        expired = [
            key
            for key, candidate in self._discovery_candidates.items()
            if now_ts - float(candidate["last_seen"])
            > DISCOVERY_CANDIDATE_TTL_SECONDS
        ]
        for key in expired:
            self._discovery_candidates.pop(key, None)

    def _candidate_confirmed(
        self,
        device_id: int,
        device_type: int,
        transmission_type: int,
        payload: bytes,
        source: str,
    ) -> bool:
        now_ts = datetime.now(timezone.utc).timestamp()
        self._expire_discovery_candidates(now_ts)

        key = (device_id, device_type, transmission_type)
        required_packets = _discovery_confirmation_packets(device_type)
        candidate = self._discovery_candidates.get(key)

        if candidate is None:
            if len(self._discovery_candidates) >= MAX_DISCOVERY_CANDIDATES:
                oldest_key = min(
                    self._discovery_candidates,
                    key=lambda item: float(
                        self._discovery_candidates[item]["last_seen"]
                    ),
                )
                self._discovery_candidates.pop(oldest_key, None)

            self._discovery_candidates[key] = {
                "count": 1,
                "first_seen": now_ts,
                "last_seen": now_ts,
                "last_payload": payload,
                "sources": {source},
            }
            _LOGGER.debug(
                "ANT+ discovery candidate %s type %s tx %s: 1/%s",
                device_id,
                device_type,
                transmission_type,
                required_packets,
            )
            return False

        first_seen = float(candidate["first_seen"])
        if now_ts - first_seen > DISCOVERY_CONFIRM_WINDOW_SECONDS:
            candidate.clear()
            candidate.update(
                {
                    "count": 1,
                    "first_seen": now_ts,
                    "last_seen": now_ts,
                    "last_payload": payload,
                    "sources": {source},
                }
            )
            return False

        candidate["count"] = int(candidate["count"]) + 1
        candidate["last_seen"] = now_ts
        candidate["last_payload"] = payload
        candidate.setdefault("sources", set()).add(source)

        count = int(candidate["count"])
        if count < required_packets:
            _LOGGER.debug(
                "ANT+ discovery candidate %s type %s tx %s: %s/%s",
                device_id,
                device_type,
                transmission_type,
                count,
                required_packets,
            )
            return False

        self._discovery_candidates.pop(key, None)
        _LOGGER.info(
            "Confirmed ANT+ RF identity %s type %s tx %s after %s packets",
            device_id,
            device_type,
            transmission_type,
            count,
        )
        return True

    def process_packet(
        self,
        device_id: int,
        device_type: int,
        transmission_type: int,
        payload: bytes,
        *,
        source: str = "unknown",
        ingress_checked: bool = False,
    ) -> None:
        """Process one ANT+ packet from any transport.

        ANT device ID is the canonical identity. If the same ANT ID is seen
        through local USB and/or multiple remote gateways, all packets update
        the same AntDevice instance.
        """
        # Accepted idle sensors still expose their own raw physical measurements,
        # but only at a bounded per-page rate. Keep this gate before diagnostics,
        # identity/capability work and decoding. Active sessions bypass it.
        page = (int(payload[0]) & 0x7F) if payload else -1
        if (
            not ingress_checked
            and self.fast_ignore_idle_packet(device_id, device_type, page)
        ):
            return

        self.diagnostics.inc("receiver_packets_seen")
        self.diagnostics.inc_profile("receiver_packets_seen", device_type)
        # One global Capture switch controls every ANT+ source.
        if not self._capture_enabled:
            return

        if not 0 <= device_id <= 0xFFFF:
            raise ValueError(f"Invalid ANT device ID: {device_id}")

        if not 0 <= device_type <= 0xFF:
            raise ValueError(f"Invalid ANT device type: {device_type}")

        if not 0 <= transmission_type <= 0xFF:
            raise ValueError(
                f"Invalid ANT transmission type: {transmission_type}"
            )

        if len(payload) != 8:
            raise ValueError(
                f"ANT payload must contain exactly 8 bytes, got {len(payload)}"
            )

        if device_id in self._forget_requested:
            with self._lock:
                self.devices.pop(device_id, None)
                for key in tuple(self._discovery_candidates):
                    if key[0] == device_id:
                        self._discovery_candidates.pop(key, None)
                for key in tuple(self._identity_candidates):
                    if key[0] == device_id:
                        self._identity_candidates.pop(key, None)
            self._forget_requested = self._forget_requested - {device_id}

        new_device = False
        new_profile = False
        metadata_changed = False

        with self._lock:
            # ANT device ID remains the canonical HA identity. A brand-new
            # device ID or a new profile on an existing device must first
            # survive RF candidate validation.
            device = self.devices.get(device_id)
            needs_confirmation = (
                device is None
                or device_type not in device.profiles
            )

            if needs_confirmation and not self._candidate_confirmed(
                device_id,
                device_type,
                transmission_type,
                payload,
                source,
            ):
                return

            if device is None:
                if len(self.devices) >= MAX_CONFIRMED_DEVICES:
                    _LOGGER.warning(
                        "ANT+ confirmed-device safety limit reached (%s); "
                        "ignoring new device %s",
                        MAX_CONFIRMED_DEVICES,
                        device_id,
                    )
                    return
                device = AntDevice(device_id=device_id)
                device.decoder_state["_diagnostics"] = self.diagnostics
                self.devices[device_id] = device
                new_device = True

            if device_type not in device.profiles:
                if len(device.profiles) >= MAX_PROFILES_PER_DEVICE:
                    _LOGGER.warning(
                        "ANT+ profile safety limit reached for device %s (%s)",
                        device_id,
                        MAX_PROFILES_PER_DEVICE,
                    )
                    return
                device.profiles.add(device_type)
                known_profiles = dict(self._known_profiles_snapshot)
                known_profiles[device_id] = frozenset(device.profiles)
                self._known_profiles_snapshot = known_profiles
                new_profile = True

            # Once the provider marks a physical sensor provisional/unaccepted,
            # ordinary RF telemetry is no longer useful. Keep only packets that
            # can establish a new ANT profile or stable common-page identity.
            #
            # ANT common pages 0x50/0x51 carry manufacturer/product identity.
            # Everything else waits until the user accepts the sensor.
            live_telemetry_enabled = device_id in self._telemetry_enabled_devices
            # Accepted physical sensors decode the sampled idle packets admitted at
            # ingress so their own HA entities remain current. Unaccepted sensors
            # still decode only structural/identity pages until the user adds them.
            telemetry_enabled = (
                live_telemetry_enabled or device_id in self._accepted_devices
            )
            page = int(payload[0]) & 0x7F
            identity_page = _is_identity_page(device_type, page)
            if not telemetry_enabled and not new_profile and not identity_page:
                self.diagnostics.inc("provisional_packets_ignored")
                return

            device.transmission_types.add(transmission_type)
            profile_tx = device.decoder_state.setdefault("profile_transmission_types", {})
            profile_tx.setdefault(device_type, set()).add(transmission_type)
            device.last_seen = datetime.now(timezone.utc)

            # Keep source information diagnostic-only. It does not participate
            # in device identity.
            sources = device.decoder_state.setdefault("sources", set())
            sources.add(source)

            metadata_changed = self._observe_metadata_candidate(
                device, device_type, payload
            )

            # Repeated ANT pages are the normal hot path. Only a genuinely new
            # observed page can change page-evidence capabilities, so avoid full
            # capability resolution for repeated telemetry packets.
            observed = device.decoder_state.get("observed_pages", {}).get(device_type, set())
            page_is_new = page not in observed
            before_capabilities = capability_signature(device) if page_is_new else None
            new_capability_page = record_observed_page(device, device_type, payload)

            changed_metrics: list[str] = []

            # Decode exactly the packet that promotes a supported semantic
            # profile, even before the user accepts the sensor. This is bounded
            # control-plane work (once per newly confirmed profile) and lets
            # profiles whose capabilities are only visible in their payload
            # advertise what they can provide without opening the telemetry hot
            # path for provisional sensors.
            discovery_decode_enabled = (
                new_profile
                and int(device_type) in SEMANTIC_DISCOVERY_PROFILE_TYPES
            )
            if telemetry_enabled or discovery_decode_enabled:
                decode_started = time.perf_counter()
                decoded_metrics = decode_packet(device, device_type, payload)
                decode_elapsed = time.perf_counter() - decode_started
                self.diagnostics.inc("decode_calls")
                self.diagnostics.inc_profile("decode_calls", device_type)
                self.diagnostics.inc("metrics_produced", len(decoded_metrics))
                self.diagnostics.add_time("decode_total", decode_elapsed)
                self.diagnostics.set_gauge("last_decode_device_type", device_type)
            else:
                decoded_metrics = []
                self.diagnostics.inc("telemetry_decode_suppressed")
                self.diagnostics.inc_profile(
                    "telemetry_decode_suppressed", device_type
                )

            # FE-C command status is authoritative capability feedback. Only this
            # page or a newly observed page can change the capability model.
            command_capability_changed = False
            if device_type == DEVICE_TYPE_FITNESS_EQUIPMENT and page == 0x47:
                command_capability_changed = record_fe_command_status(
                    device, payload[1], payload[3]
                )

            capability_changed = command_capability_changed
            if new_capability_page and before_capabilities is not None:
                capability_changed = (
                    capability_signature(device) != before_capabilities
                ) or capability_changed

            for metric in decoded_metrics:
                old = device.metrics.get(metric.key)

                if old is None and len(device.metrics) >= MAX_METRICS_PER_DEVICE:
                    _LOGGER.warning(
                        "ANT+ metric safety limit reached for device %s (%s)",
                        device_id,
                        MAX_METRICS_PER_DEVICE,
                    )
                    continue

                device.metrics[metric.key] = metric

                if old is None or (
                    old.value != metric.value
                    or old.unit != metric.unit
                    or old.device_class != metric.device_class
                    or old.state_class != metric.state_class
                    or old.icon != metric.icon
                    or old.entity_category != metric.entity_category
                    or old.enabled_default != metric.enabled_default
                    or old.availability_mode != metric.availability_mode
                ):
                    changed_metrics.append(metric.key)

        if telemetry_enabled or int(device_type) in (16, 115):
            for callback in tuple(self._packet_callbacks):
                try:
                    callback(
                        device, device_type, transmission_type, payload, source
                    )
                except Exception:
                    _LOGGER.debug("ANT+ packet callback failed", exc_info=True)

        if new_device:
            _LOGGER.info(
                "Discovered ANT+ device %s via %s",
                device_id,
                source,
            )

        if new_profile:
            _LOGGER.info(
                "ANT+ device %s exposed profile %s (%s) via %s",
                device_id,
                device_type,
                DEVICE_TYPE_NAMES.get(device_type, "Unknown"),
                source,
            )

        if new_device or new_profile or metadata_changed or capability_changed:
            for callback in tuple(self._device_callbacks):
                try:
                    callback(device)
                except Exception:
                    _LOGGER.debug(
                        "ANT+ device callback failed",
                        exc_info=True,
                    )

        self.diagnostics.inc("metrics_changed", len(changed_metrics))
        callback_key: str | None = None
        now_mono = time.monotonic()
        if changed_metrics:
            # Provider consumers only need the newest device snapshot. Emitting
            # one callback per changed metric multiplies lock/scheduler/GIL work
            # for multi-metric packets without preserving any extra information.
            callback_key = changed_metrics[-1]
            self._last_presence_callback_monotonic[device_id] = now_mono
        elif device_id in self._accepted_devices:
            last_presence = self._last_presence_callback_monotonic.get(device_id, 0.0)
            if now_mono - last_presence >= ANT_LAST_SEEN_CALLBACK_INTERVAL_SECONDS:
                # No metric changed, but RF traffic is alive. One synthetic
                # low-rate callback lets the provider advance endpoint.last_seen.
                callback_key = "__last_seen__"
                self._last_presence_callback_monotonic[device_id] = now_mono

        if callback_key is not None:
            for callback in tuple(self._metric_callbacks):
                try:
                    callback(device, callback_key)
                except Exception:
                    _LOGGER.debug(
                        "ANT+ metric callback failed",
                        exc_info=True,
                    )

    def _metadata_candidate(
        self, device_id: int, device_type: int, data: bytes
    ) -> dict[str, object]:
        """Decode only identity layouts explicitly supported by this profile."""
        page = data[0] & 0x7F
        candidate: dict[str, object] = {}

        if (
            device_type in COMMON_IDENTITY_PAGE_PROFILES
            and page == 80
        ):
            hardware_rev = data[3]
            manufacturer_id = data[4] | (data[5] << 8)
            model_no = data[6] | (data[7] << 8)

            if hardware_rev != 0xFF:
                candidate["hardware_rev"] = hardware_rev
            if manufacturer_id != 0xFFFF:
                candidate["manufacturer_id"] = manufacturer_id
                candidate["manufacturer_name"] = (
                    catalog_manufacturer_name("antplus", manufacturer_id)
                    or f"ANT manufacturer {manufacturer_id}"
                )
            if model_no != 0xFFFF:
                candidate["model_no"] = model_no

        elif (
            device_type in COMMON_IDENTITY_PAGE_PROFILES
            and page == 81
        ):
            sw_rev = data[2]
            sw_main = data[3]
            serial_no = int.from_bytes(data[4:8], byteorder="little")

            if not (sw_rev == 0xFF and sw_main == 0xFF):
                candidate["software_ver"] = (
                    str(sw_main / 10)
                    if sw_rev == 0xFF
                    else str((sw_main * 100 + sw_rev) / 1000)
                )
            if serial_no != 0xFFFFFFFF:
                candidate["serial_no"] = serial_no

        # Bicycle speed/cadence individual-profile background pages use a
        # profile-specific identity layout, not ANT Common Pages 80/81. The same
        # layout is accepted for combined BSC devices when they actually emit
        # these standardized background pages.
        elif device_type in BSC_IDENTITY_PAGE_PROFILES and page == 2:
            manufacturer_id = data[1]
            serial_no = data[2] | (data[3] << 8)
            if manufacturer_id != 0xFF:
                candidate["manufacturer_id"] = manufacturer_id
                candidate["manufacturer_name"] = (
                    catalog_manufacturer_name("antplus", manufacturer_id)
                    or f"ANT manufacturer {manufacturer_id}"
                )
            if serial_no != 0xFFFF:
                candidate["serial_no"] = serial_no

        elif device_type in BSC_IDENTITY_PAGE_PROFILES and page == 3:
            hardware_rev = data[1]
            software_rev = data[2]
            model_no = data[3]
            if hardware_rev != 0xFF:
                candidate["hardware_rev"] = hardware_rev
            if software_rev != 0xFF:
                candidate["software_ver"] = str(software_rev)
            if model_no != 0xFF:
                candidate["model_no"] = model_no

        # HRM identification is part of profile pages 2/3 rather than inferred
        # from generic common-page numbers.
        elif device_type == DEVICE_TYPE_HEART_RATE and page == 2:
            manufacturer_id = data[1]
            serial_upper = data[2] | (data[3] << 8)
            if manufacturer_id != 0xFF:
                candidate["manufacturer_id"] = manufacturer_id
                candidate["manufacturer_name"] = (
                    catalog_manufacturer_name("antplus", manufacturer_id)
                    or f"ANT manufacturer {manufacturer_id}"
                )
            if serial_upper != 0xFFFF:
                # ANT+ HRM page 2 carries only the upper 16 bits of the serial.
                # The ANT channel device number is the lower 16 bits.  Persist the
                # complete 32-bit serial so it can be compared with Bluetooth DIS
                # identity from the same dual-protocol physical device.
                candidate["serial_no"] = (
                    (int(serial_upper) << 16) | (int(device_id) & 0xFFFF)
                )

        elif device_type == DEVICE_TYPE_HEART_RATE and page == 3:
            hardware_rev = data[1]
            software_rev = data[2]
            model_no = data[3]
            if hardware_rev != 0xFF:
                candidate["hardware_rev"] = hardware_rev
            if software_rev != 0xFF:
                candidate["software_ver"] = str(software_rev)
            if model_no != 0xFF:
                candidate["model_no"] = model_no

        return candidate

    def _observe_metadata_candidate(
        self, device: AntDevice, device_type: int, data: bytes
    ) -> bool:
        """Commit structural identity only after repeated identical evidence."""
        candidate = self._metadata_candidate(device.device_id, device_type, data)
        if not candidate:
            return False

        page = int(data[0]) & 0x7F
        key = (int(device.device_id), int(device_type), page)
        signature = tuple(sorted(candidate.items()))
        previous = self._identity_candidates.get(key)
        count = previous[1] + 1 if previous and previous[0] == signature else 1
        self._identity_candidates[key] = (signature, count)
        # RF identity has already survived the profile-aware multi-packet guard.
        # Serial-bearing identity pages are therefore safe to accept on their
        # first valid observation; waiting for a second slow background cycle only
        # delays cross-transport merge. Non-serial product/version pages retain
        # the repeated-evidence guard.
        serial_identity_page = (
            int(device_type) == DEVICE_TYPE_HEART_RATE and page == 2
        ) or (
            int(device_type) in BSC_IDENTITY_PAGE_PROFILES and page == 2
        ) or (
            int(device_type) in COMMON_IDENTITY_PAGE_PROFILES and page == 0x51
        )
        required_observations = (
            1 if serial_identity_page else IDENTITY_CONFIRM_OBSERVATIONS
        )
        if count < required_observations:
            return False

        changed = False
        for attr, value in candidate.items():
            if getattr(device, attr) != value:
                setattr(device, attr, value)
                changed = True
        return changed



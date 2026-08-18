"""Connection-scoped Garmin GFDI transports and read-only file synchronization."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import struct
from typing import Any, Callable

from .protocol import (
    GARMIN_EPOCH_OFFSET,
    GARMIN_GFDI_V0_RECEIVE_UUID,
    GARMIN_GFDI_V0_SEND_UUID,
    GARMIN_GFDI_V1_RECEIVE_UUID,
    GARMIN_GFDI_V1_SEND_UUID,
    GARMIN_UUID_SUFFIX,
    GFDI_AUTH_NEGOTIATION,
    GFDI_CONFIGURATION,
    GFDI_CURRENT_TIME_REQUEST,
    GFDI_DEVICE_INFORMATION,
    GFDI_DEVICE_SETTINGS,
    GFDI_DOWNLOAD_REQUEST,
    GFDI_FILE_TRANSFER_DATA,
    GFDI_MUSIC_CONTROL_CAPABILITIES,
    GFDI_NOTIFICATION_SUBSCRIPTION,
    GFDI_PROTOBUF_REQUEST,
    GFDI_PROTOBUF_RESPONSE,
    GFDI_RESPONSE,
    GFDI_SYSTEM_EVENT,
    GarminCobsStream,
    GarminDirectoryEntry,
    GarminProtocolError,
    GarminProtocolLimitError,
    GarminSyncFile,
    GarminUnsupportedTransport,
    ProtobufReassembler,
    STATUS_ACK,
    STATUS_NAK,
    STATUS_UNSUPPORTED,
    build_download_request,
    build_file_list_request,
    build_file_request,
    build_file_transfer_ack,
    build_generic_status,
    build_gfdi,
    build_protobuf_chunk_ack,
    build_protobuf_message,
    crc16,
    garmin_cobs_encode,
    normalize_bluetooth_uuid,
    parse_directory,
    parse_download_status,
    parse_file_list_response,
    parse_file_response,
    parse_file_transfer,
    parse_gfdi,
    parse_protobuf_wrapper,
)

_LOGGER = logging.getLogger(__name__)

BLE_IO_TIMEOUT = 10.0
HANDSHAKE_TIMEOUT = 24.0
MESSAGE_TIMEOUT = 12.0
PROTOBUF_EXCHANGE_TIMEOUT = 30.0
LEGACY_FLUSH_TIMEOUT = 10.0
FILE_TRANSFER_TIMEOUT = 60.0
CLOSE_TIMEOUT = 5.0
GFDI_QUEUE_LIMIT = 128
MANAGEMENT_QUEUE_LIMIT = 32
MAX_LEGACY_FILE_BYTES = 32 * 1024 * 1024
MAX_COMPRESSED_FILE_BYTES = 16 * 1024 * 1024
MAX_FILE_LIST_PAGES = 8
MAX_CURSOR_PAGES = 16
MAX_FILES_PER_LISTING = 1_000
SAFE_GATT_WRITE = 20
V2_CLIENT_ID = 2
V2_GFDI_SERVICE = 1
V2_FILE_SERVICES = (0x2018, 0x4018, 0x6018, 0xA018, 0xC018, 0xE018)
MAX_TRANSPORT_CANDIDATES = 6
MAX_V2_CHANNEL_CANDIDATES = 4


@dataclass(slots=True)
class GarminDownloadedFile:
    key: str
    data: bytes
    size: int
    type_name: str
    page_id: int | None = None


def _all_characteristics(client) -> dict[str, Any]:
    result: dict[str, Any] = {}
    services = getattr(client, "services", None)
    if services is None:
        return result
    try:
        service_iter = list(services)
    except TypeError:
        service_iter = list(getattr(services, "services", {}).values())
    for service in service_iter:
        for char in getattr(service, "characteristics", []) or []:
            uuid = normalize_bluetooth_uuid(getattr(char, "uuid", ""))
            if uuid:
                result[uuid] = char
    return result


def _properties(char: Any) -> set[str]:
    return {str(value).lower() for value in (getattr(char, "properties", None) or [])}


class BaseGarminTransport:
    backend = "gfdi_unknown"
    supports_service_transfer = False

    def __init__(self, client) -> None:
        self.client = client
        self._gfdi_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue(maxsize=GFDI_QUEUE_LIMIT)
        self._stream = GarminCobsStream()
        self._overflow_error: Exception | None = None
        self._write_lock = asyncio.Lock()
        self.max_write_size = SAFE_GATT_WRITE
        self._started = False

    def _queue_gfdi_frame(self, frame: bytes) -> None:
        try:
            message = parse_gfdi(frame)
        except Exception as err:
            self._overflow_error = err
            return
        if self._gfdi_queue.full():
            self._overflow_error = GarminProtocolLimitError("Garmin GFDI queue overflow")
            return
        self._gfdi_queue.put_nowait(message)

    def _feed_cobs(self, payload: bytes) -> None:
        try:
            for frame in self._stream.feed(payload):
                self._queue_gfdi_frame(frame)
        except Exception as err:
            self._overflow_error = err

    async def async_start(self) -> None:
        raise NotImplementedError

    async def async_send_gfdi(self, frame: bytes) -> None:
        raise NotImplementedError

    async def async_read_gfdi(self, timeout: float = MESSAGE_TIMEOUT) -> tuple[int, bytes]:
        if self._overflow_error is not None:
            err = self._overflow_error
            self._overflow_error = None
            raise err
        async with asyncio.timeout(timeout):
            result = await self._gfdi_queue.get()
        if self._overflow_error is not None:
            err = self._overflow_error
            self._overflow_error = None
            raise err
        return result

    async def async_stop(self) -> None:
        self._started = False

    async def async_download_service_file(
        self,
        temporary_handle: int,
        *,
        progress: Callable[[int], None] | None = None,
    ) -> bytes:
        raise GarminUnsupportedTransport("this Garmin transport has no V2 file service")


class GarminV1Transport(BaseGarminTransport):
    """Direct V0/V1 GFDI characteristic transport."""

    def __init__(self, client, send_uuid: str, receive_uuid: str, backend: str) -> None:
        super().__init__(client)
        self.send_uuid = send_uuid
        self.receive_uuid = receive_uuid
        self.backend = backend

    @classmethod
    def candidates_from_client(cls, client) -> tuple["GarminV1Transport", ...]:
        """Return every direct V1/V0 transport exposed by connected GATT."""
        chars = _all_characteristics(client)
        result: list[GarminV1Transport] = []
        if GARMIN_GFDI_V1_SEND_UUID in chars and GARMIN_GFDI_V1_RECEIVE_UUID in chars:
            result.append(
                cls(client, GARMIN_GFDI_V1_SEND_UUID, GARMIN_GFDI_V1_RECEIVE_UUID, "gfdi_v1")
            )
        if GARMIN_GFDI_V0_SEND_UUID in chars and GARMIN_GFDI_V0_RECEIVE_UUID in chars:
            result.append(
                cls(client, GARMIN_GFDI_V0_SEND_UUID, GARMIN_GFDI_V0_RECEIVE_UUID, "gfdi_v0")
            )
        return tuple(result)

    @classmethod
    def from_client(cls, client) -> "GarminV1Transport | None":
        candidates = cls.candidates_from_client(client)
        return candidates[0] if candidates else None

    async def async_start(self) -> None:
        async with asyncio.timeout(BLE_IO_TIMEOUT):
            await self.client.start_notify(self.receive_uuid, self._on_notify)
        self._started = True

    def _on_notify(self, _sender, data: bytearray) -> None:
        self._feed_cobs(bytes(data))

    async def async_send_gfdi(self, frame: bytes) -> None:
        encoded = garmin_cobs_encode(frame)
        async with self._write_lock:
            for offset in range(0, len(encoded), self.max_write_size):
                chunk = encoded[offset : offset + self.max_write_size]
                async with asyncio.timeout(BLE_IO_TIMEOUT):
                    await self.client.write_gatt_char(self.send_uuid, chunk, response=False)

    async def async_stop(self) -> None:
        if self._started:
            try:
                async with asyncio.timeout(CLOSE_TIMEOUT):
                    await self.client.stop_notify(self.receive_uuid)
            except Exception:
                pass
        await super().async_stop()


@dataclass(slots=True)
class _ServiceCollector:
    service: int
    handle: int
    closed: asyncio.Event
    data: bytearray
    first_message_seen: bool = False
    error: Exception | None = None
    last_progress: int = 0


class GarminV2Transport(BaseGarminTransport):
    """Garmin Multi-Link V2 with fail-fast handling for unverified MLR mode."""

    backend = "gfdi_v2_ml"
    supports_service_transfer = True

    def __init__(self, client, receive_uuid: str, send_uuid: str) -> None:
        super().__init__(client)
        self.receive_uuid = receive_uuid
        self.send_uuid = send_uuid
        self._management_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=MANAGEMENT_QUEUE_LIMIT)
        self._service_by_handle: dict[int, int] = {}
        self._gfdi_handle: int | None = None
        self._collector: _ServiceCollector | None = None

    @classmethod
    def candidates_from_client(cls, client) -> tuple["GarminV2Transport", ...]:
        """Return bounded Multi-Link channel pairs discovered from GATT.

        Garmin channel selection is derived from the 281x/282x characteristic
        pair actually exposed by the device.  The full hexadecimal channel nibble
        is accepted; there is no product generation or model-name table.
        """
        chars = _all_characteristics(client)
        pairs: list[tuple[int, str, str]] = []
        for receive, receive_char in chars.items():
            short = receive.split("-", 1)[0]
            if (
                len(short) != 8
                or not short.startswith("6a4e281")
                or short[-1] not in "0123456789abcdef"
                or not receive.endswith(GARMIN_UUID_SUFFIX)
            ):
                continue
            channel = short[-1]
            send = f"6a4e282{channel}{GARMIN_UUID_SUFFIX}"
            send_char = chars.get(send)
            if send_char is None:
                continue
            receive_props = _properties(receive_char)
            send_props = _properties(send_char)
            if receive_props and not ({"notify", "indicate"} & receive_props):
                continue
            if send_props and not ({"write", "write-without-response"} & send_props):
                continue
            pairs.append((int(channel, 16), receive, send))

        pairs.sort(key=lambda item: item[0])
        return tuple(
            cls(client, receive, send)
            for _index, receive, send in pairs[:MAX_V2_CHANNEL_CANDIDATES]
        )

    @classmethod
    def from_client(cls, client) -> "GarminV2Transport | None":
        candidates = cls.candidates_from_client(client)
        return candidates[0] if candidates else None

    def _on_notify(self, _sender, data: bytearray) -> None:
        payload = bytes(data)
        if not payload:
            return
        handle = payload[0]
        body = payload[1:]
        if handle == 0:
            if self._management_queue.full():
                self._overflow_error = GarminProtocolLimitError("Garmin V2 management queue overflow")
                return
            self._management_queue.put_nowait(body)
            self._observe_management(body)
            return
        if self._gfdi_handle is not None and handle == self._gfdi_handle:
            self._feed_cobs(body)
            return
        collector = self._collector
        if collector is None or handle != collector.handle:
            return
        if collector.error is not None:
            return
        if not collector.first_message_seen:
            collector.first_message_seen = True
            if body != b"\x00\x00\x00":
                collector.error = GarminProtocolError("unexpected Garmin V2 file-service greeting")
                collector.closed.set()
            return
        if len(collector.data) + len(body) > MAX_COMPRESSED_FILE_BYTES:
            collector.error = GarminProtocolLimitError("compressed Garmin activity exceeds safe limit")
            collector.closed.set()
            return
        collector.data.extend(body)

    def _observe_management(self, body: bytes) -> None:
        if len(body) < 9:
            return
        request_type = body[0]
        client_id = struct.unpack_from("<Q", body, 1)[0]
        if client_id != V2_CLIENT_ID:
            return
        if request_type == 1 and len(body) >= 14:  # register response
            service, status, handle, _reliable = struct.unpack_from("<HBBB", body, 9)
            if status == 0:
                self._service_by_handle[handle] = service
                if service == V2_GFDI_SERVICE:
                    self._gfdi_handle = handle
        elif request_type == 3 and len(body) >= 13:  # close response
            service, handle, status = struct.unpack_from("<HBB", body, 9)
            self._service_by_handle.pop(handle, None)
            if handle == self._gfdi_handle:
                self._gfdi_handle = None
            collector = self._collector
            if collector is not None and collector.handle == handle and collector.service == service:
                if status != 0 and collector.error is None:
                    collector.error = GarminProtocolError(
                        f"Garmin V2 file service 0x{service:04x} closed with status {status}"
                    )
                collector.closed.set()
        elif request_type == 6:  # close-all response
            self._service_by_handle.clear()
            self._gfdi_handle = None
            if self._collector is not None:
                self._collector.closed.set()

    async def _write_packet(self, payload: bytes) -> None:
        async with asyncio.timeout(BLE_IO_TIMEOUT):
            await self.client.write_gatt_char(self.send_uuid, payload, response=False)

    async def _wait_management(self, predicate, timeout: float = BLE_IO_TIMEOUT) -> bytes:
        async with asyncio.timeout(timeout):
            while True:
                body = await self._management_queue.get()
                if predicate(body):
                    return body

    @staticmethod
    def _management_request(request_type: int, tail: bytes) -> bytes:
        return bytes([0, request_type]) + struct.pack("<Q", V2_CLIENT_ID) + tail

    async def async_register_service(self, service: int) -> tuple[int, int]:
        request = self._management_request(0, struct.pack("<HB", service & 0xFFFF, 0))
        async with self._write_lock:
            await self._write_packet(request)
            response = await self._wait_management(
                lambda body: len(body) >= 14
                and body[0] == 1
                and struct.unpack_from("<Q", body, 1)[0] == V2_CLIENT_ID
                and struct.unpack_from("<H", body, 9)[0] == (service & 0xFFFF)
            )
        _service, status, handle, reliable = struct.unpack_from("<HBBB", response, 9)
        if status != 0:
            raise GarminProtocolError(f"Garmin service 0x{service:04x} registration failed ({status})")
        if reliable != 0:
            # Do not attempt MLR with unverified flow control. Failing here is far
            # safer than leaving an HA Bluetooth task waiting indefinitely.
            try:
                await self.async_close_service(service, handle)
            except Exception:
                pass
            raise GarminUnsupportedTransport("Garmin MLR reliable mode is not implemented")
        return handle, reliable

    async def async_close_service(self, service: int, handle: int) -> None:
        request = self._management_request(2, struct.pack("<HB", service & 0xFFFF, handle & 0xFF))
        async with self._write_lock:
            await self._write_packet(request)
            try:
                await self._wait_management(
                    lambda body: len(body) >= 13
                    and body[0] == 3
                    and struct.unpack_from("<H", body, 9)[0] == (service & 0xFFFF)
                    and body[11] == (handle & 0xFF),
                    timeout=CLOSE_TIMEOUT,
                )
            except TimeoutError:
                pass
        self._service_by_handle.pop(handle, None)
        if handle == self._gfdi_handle:
            self._gfdi_handle = None

    async def async_start(self) -> None:
        async with asyncio.timeout(BLE_IO_TIMEOUT):
            await self.client.start_notify(self.receive_uuid, self._on_notify)
        self._started = True

        # A stale phone/app session can leave service handles behind. Request a
        # clean client namespace, but do not make that response a hard dependency.
        # Garmin V2 close-all is a 13-byte management packet; the final zero is
        # reserved but part of the on-wire request on known implementations.
        close_all = self._management_request(5, b"\x00\x00\x00")
        async with self._write_lock:
            await self._write_packet(close_all)
            try:
                await self._wait_management(lambda body: len(body) >= 9 and body[0] == 6, timeout=4.0)
            except TimeoutError:
                pass
        self._gfdi_handle, _ = await self.async_register_service(V2_GFDI_SERVICE)

    async def async_send_gfdi(self, frame: bytes) -> None:
        handle = self._gfdi_handle
        if handle is None:
            raise GarminProtocolError("Garmin GFDI service is not registered")
        encoded = garmin_cobs_encode(frame)
        chunk_size = max(1, self.max_write_size - 1)
        async with self._write_lock:
            for offset in range(0, len(encoded), chunk_size):
                await self._write_packet(bytes([handle]) + encoded[offset : offset + chunk_size])

    async def _write_service(self, handle: int, payload: bytes) -> None:
        chunk_size = max(1, self.max_write_size - 1)
        async with self._write_lock:
            for offset in range(0, len(payload), chunk_size):
                await self._write_packet(bytes([handle]) + payload[offset : offset + chunk_size])

    async def async_download_service_file(
        self,
        temporary_handle: int,
        *,
        progress: Callable[[int], None] | None = None,
    ) -> bytes:
        service = next((candidate for candidate in V2_FILE_SERVICES if candidate not in self._service_by_handle.values()), None)
        if service is None:
            raise GarminProtocolError("no free Garmin V2 file-transfer service")
        handle, _reliable = await self.async_register_service(service)
        collector = _ServiceCollector(service, handle, asyncio.Event(), bytearray())
        self._collector = collector
        try:
            request = struct.pack("<BBHBB", 0, 0, int(temporary_handle) & 0xFFFF, 0, 0)
            await self._write_service(handle, request)
            async with asyncio.timeout(FILE_TRANSFER_TIMEOUT):
                while not collector.closed.is_set():
                    try:
                        await asyncio.wait_for(collector.closed.wait(), timeout=2.0)
                    except TimeoutError:
                        if progress is not None and len(collector.data) != collector.last_progress:
                            collector.last_progress = len(collector.data)
                            progress(len(collector.data))
            if collector.error is not None:
                raise collector.error
            if not collector.first_message_seen:
                raise GarminProtocolError("Garmin file service closed before greeting")
            if not collector.data:
                raise GarminProtocolError("Garmin file service returned no compressed data")
            return bytes(collector.data)
        finally:
            self._collector = None
            if handle in self._service_by_handle:
                try:
                    async with asyncio.timeout(CLOSE_TIMEOUT + 1):
                        await self.async_close_service(service, handle)
                except Exception:
                    pass

    async def async_stop(self) -> None:
        collector = self._collector
        if collector is not None:
            collector.closed.set()
            self._collector = None
        if self._gfdi_handle is not None:
            try:
                await self.async_close_service(V2_GFDI_SERVICE, self._gfdi_handle)
            except Exception:
                pass
        if self._started:
            try:
                async with asyncio.timeout(CLOSE_TIMEOUT):
                    await self.client.stop_notify(self.receive_uuid)
            except Exception:
                pass
        await super().async_stop()


def transport_candidates_from_client(client) -> tuple[BaseGarminTransport, ...]:
    """Return bounded protocol candidates ordered by capability preference.

    V2 is tried first, followed by direct V1 then V0.  Multiple advertised V2
    Multi-Link channels can be tried safely by the coordinator if an earlier
    channel does not complete the bounded handshake.
    """
    candidates: list[BaseGarminTransport] = []
    candidates.extend(GarminV2Transport.candidates_from_client(client))
    candidates.extend(GarminV1Transport.candidates_from_client(client))
    return tuple(candidates[:MAX_TRANSPORT_CANDIDATES])


def transport_capabilities_from_client(client) -> tuple[str, ...]:
    """Return unique backend names for diagnostics without starting a session."""
    result: list[str] = []
    for candidate in transport_candidates_from_client(client):
        if candidate.backend not in result:
            result.append(candidate.backend)
    return tuple(result)


def transport_from_client(client) -> BaseGarminTransport:
    """Select the preferred transport by GATT capability, never model name."""
    candidates = transport_candidates_from_client(client)
    if candidates:
        return candidates[0]
    raise GarminUnsupportedTransport("no supported Garmin GFDI V0/V1/V2 characteristics")


class GarminGfdiSession:
    """Read-only Garmin session with bounded handshake and file operations."""

    def __init__(self, transport: BaseGarminTransport) -> None:
        self.transport = transport
        self.protocol_version: int | None = None
        self.capabilities: bytes = b""
        self._request_id = 300
        self._ready = False

    def next_request_id(self) -> int:
        self._request_id = 1 if self._request_id >= 0xFFFE else self._request_id + 1
        return self._request_id

    async def _send(self, frame: bytes) -> None:
        await self.transport.async_send_gfdi(frame)

    async def _handle_housekeeping(self, message_type: int, payload: bytes) -> bool:
        """Handle watch-originated control messages; return True when consumed."""
        if message_type == GFDI_DEVICE_INFORMATION:
            if len(payload) >= 2:
                self.protocol_version = struct.unpack_from("<H", payload, 0)[0]
            await self._send(build_generic_status(message_type))
            return True

        if message_type == GFDI_CONFIGURATION:
            count = payload[0] if payload else 0
            if count > len(payload) - 1:
                raise GarminProtocolError("truncated Garmin capability message")
            self.capabilities = bytes(payload[1 : 1 + count])
            await self._send(build_generic_status(message_type))
            # Echo a conservative capability envelope rather than claiming device
            # features HA-Fitness does not use.
            await self._send(build_gfdi(GFDI_CONFIGURATION, bytes([len(self.capabilities)]) + self.capabilities))
            # AUTO_UPLOAD=true, WEATHER_CONDITIONS=true, WEATHER_ALERTS=false.
            await self._send(build_gfdi(GFDI_DEVICE_SETTINGS, bytes([3, 6, 1, 1, 7, 1, 1, 8, 1, 0])))
            await self._send(build_gfdi(GFDI_SYSTEM_EVENT, bytes([8, 0])))
            self._ready = True
            return True

        if message_type == GFDI_AUTH_NEGOTIATION:
            unknown = payload[0] if payload else 0
            flags = struct.unpack_from("<I", payload + b"\x00\x00\x00\x00", 1)[0] if payload else 0
            # GUESS_OK=0, preserve the watch's unknown byte and requested flags.
            await self._send(build_generic_status(message_type, STATUS_ACK, bytes([0, unknown]) + struct.pack("<I", flags)))
            return True

        if message_type == GFDI_CURRENT_TIME_REQUEST:
            if len(payload) < 4:
                await self._send(build_generic_status(message_type, STATUS_NAK))
                return True
            reference = struct.unpack_from("<I", payload, 0)[0]
            now = datetime.now(timezone.utc)
            garmin_now = max(0, int(now.timestamp()) - GARMIN_EPOCH_OFFSET)
            local = datetime.now().astimezone()
            offset = int((local.utcoffset() or timezone.utc.utcoffset(local)).total_seconds())
            extra = struct.pack("<IIiII", reference, garmin_now, offset, 0, 0)
            await self._send(build_generic_status(message_type, STATUS_ACK, extra))
            return True

        if message_type == GFDI_NOTIFICATION_SUBSCRIPTION:
            enable = 1 if payload and payload[0] == 1 else 0
            unknown = payload[1] if len(payload) > 1 else 0
            notification_status = 0 if enable else 1
            await self._send(build_generic_status(message_type, STATUS_ACK, bytes([notification_status, enable, unknown])))
            return True

        if message_type in {GFDI_PROTOBUF_REQUEST, GFDI_MUSIC_CONTROL_CAPABILITIES}:
            # Workout sync does not impersonate Garmin Connect's unrelated app
            # services. Explicitly reject them so the watch can continue rather
            # than retrying indefinitely.
            await self._send(build_generic_status(message_type, STATUS_UNSUPPORTED))
            return True

        return False

    async def async_start(self) -> None:
        await self.transport.async_start()
        async with asyncio.timeout(HANDSHAKE_TIMEOUT):
            while not self._ready:
                message_type, payload = await self.transport.async_read_gfdi(timeout=MESSAGE_TIMEOUT)
                if not await self._handle_housekeeping(message_type, payload):
                    if message_type != GFDI_RESPONSE:
                        await self._send(build_generic_status(message_type, STATUS_UNSUPPORTED))
        # Give immediate post-ready requests a short bounded drain window.
        end = asyncio.get_running_loop().time() + 0.25
        while asyncio.get_running_loop().time() < end:
            try:
                message_type, payload = await self.transport.async_read_gfdi(timeout=0.05)
            except TimeoutError:
                break
            await self._handle_housekeeping(message_type, payload)

    async def async_stop(self) -> None:
        await self.transport.async_stop()

    async def _next_relevant(self, predicate, *, timeout: float) -> tuple[int, bytes]:
        async with asyncio.timeout(timeout):
            while True:
                message_type, payload = await self.transport.async_read_gfdi(timeout=min(MESSAGE_TIMEOUT, timeout))
                if predicate(message_type, payload):
                    return message_type, payload
                if await self._handle_housekeeping(message_type, payload):
                    continue
                if message_type != GFDI_RESPONSE:
                    await self._send(build_generic_status(message_type, STATUS_UNSUPPORTED))

    async def async_download_legacy(self, index: int, *, max_bytes: int = MAX_LEGACY_FILE_BYTES, timeout: float = FILE_TRANSFER_TIMEOUT) -> bytes:
        """Download one classic GFDI directory/file with rolling CRC checks."""
        await self._send(build_download_request(index))
        _type, response = await self._next_relevant(
            lambda kind, payload: kind == GFDI_RESPONSE and len(payload) >= 2 and struct.unpack_from("<H", payload, 0)[0] == GFDI_DOWNLOAD_REQUEST,
            timeout=min(timeout, MESSAGE_TIMEOUT),
        )
        status, download_status, size = parse_download_status(response)
        if status != STATUS_ACK or download_status != 0:
            raise GarminProtocolError(f"Garmin legacy download rejected status={status}/{download_status}")
        if size < 0 or size > max_bytes:
            raise GarminProtocolLimitError("Garmin legacy file exceeds safe limit")
        data = bytearray()
        running_crc = 0
        async with asyncio.timeout(timeout):
            while len(data) < size:
                _kind, chunk_payload = await self._next_relevant(
                    lambda kind, _payload: kind == GFDI_FILE_TRANSFER_DATA,
                    timeout=MESSAGE_TIMEOUT,
                )
                expected_crc, offset, chunk = parse_file_transfer(chunk_payload)
                if offset != len(data):
                    raise GarminProtocolError("Garmin legacy file offset mismatch")
                if len(data) + len(chunk) > size or len(data) + len(chunk) > max_bytes:
                    raise GarminProtocolLimitError("Garmin legacy file exceeded announced size")
                actual_crc = crc16(chunk, running_crc)
                if actual_crc != expected_crc:
                    raise GarminProtocolError("Garmin legacy file CRC mismatch")
                running_crc = actual_crc
                data.extend(chunk)
                await self._send(build_file_transfer_ack(len(data)))
        if len(data) != size:
            raise GarminProtocolError("Garmin legacy file ended at wrong size")
        return bytes(data)

    async def async_best_effort_flush(self) -> None:
        try:
            await self.async_download_legacy(0, max_bytes=512 * 1024, timeout=LEGACY_FLUSH_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Modern FileSync remains authoritative; the root request is merely a
            # bounded hint that makes some firmware flush current archive state.
            _LOGGER.debug("Garmin legacy root flush unavailable", exc_info=True)

    async def _protobuf_exchange(self, smart: bytes) -> bytes:
        request_id = self.next_request_id()
        await self._send(build_protobuf_message(GFDI_PROTOBUF_REQUEST, request_id, smart))
        reassembler = ProtobufReassembler()
        async with asyncio.timeout(PROTOBUF_EXCHANGE_TIMEOUT):
            while True:
                message_type, payload = await self.transport.async_read_gfdi(timeout=MESSAGE_TIMEOUT)
                if message_type == GFDI_PROTOBUF_RESPONSE:
                    incoming_id, offset, total, fragment = parse_protobuf_wrapper(payload)
                    if incoming_id != request_id:
                        # It belongs to another request; acknowledge safely but do
                        # not mix it into this bounded reassembler.
                        if offset == 0 and len(fragment) == total:
                            await self._send(build_generic_status(message_type))
                        else:
                            await self._send(build_protobuf_chunk_ack(incoming_id, offset))
                        continue
                    if offset == 0 and len(fragment) == total:
                        await self._send(build_generic_status(message_type))
                    else:
                        await self._send(build_protobuf_chunk_ack(incoming_id, offset))
                    _rid, complete = reassembler.add(payload)
                    if complete is not None:
                        return complete
                    continue
                if await self._handle_housekeeping(message_type, payload):
                    continue
                if message_type != GFDI_RESPONSE:
                    await self._send(build_generic_status(message_type, STATUS_UNSUPPORTED))
        raise TimeoutError("Garmin protobuf exchange timed out")

    async def async_modern_file_list(self) -> list[GarminSyncFile]:
        """List a bounded amount of historical FileSync records without marking sync flags."""
        files: dict[str, GarminSyncFile] = {}
        seen_start_pages: set[int] = set()
        start_page: int | None = None
        history_pages = 0
        while history_pages < MAX_FILE_LIST_PAGES and len(files) < MAX_FILES_PER_LISTING:
            history_pages += 1
            cursor: int | None = None
            cursor_pages = 0
            next_page: int | None = None
            while cursor_pages < MAX_CURSOR_PAGES and len(files) < MAX_FILES_PER_LISTING:
                smart = build_file_list_request(cursor_id=cursor, start_page_id=start_page if cursor is None else None)
                response = await self._protobuf_exchange(smart)
                page_files, response_cursor, response_next = parse_file_list_response(response)
                for item in page_files:
                    files.setdefault(item.file_id.key, item)
                    if len(files) >= MAX_FILES_PER_LISTING:
                        break
                next_page = response_next
                if response_cursor is None:
                    break
                cursor_pages += 1
                cursor = response_cursor
            if cursor_pages >= MAX_CURSOR_PAGES:
                raise GarminProtocolLimitError("Garmin FileSync cursor page limit exceeded")
            if next_page is None or next_page in seen_start_pages:
                break
            seen_start_pages.add(next_page)
            start_page = next_page
        return list(files.values())

    async def async_request_modern_file(self, file: GarminSyncFile) -> int:
        response = await self._protobuf_exchange(build_file_request(file))
        status, handle = parse_file_response(response)
        if status != 0 or handle is None:
            raise GarminProtocolError(f"Garmin FileRequest failed status={status}")
        return handle

    async def async_activity_catalog(self) -> tuple[str, list[GarminSyncFile | GarminDirectoryEntry]]:
        """Return (mode, activity records), preferring modern read-only FileSync."""
        await self.async_best_effort_flush()
        if self.transport.supports_service_transfer:
            try:
                modern = await self.async_modern_file_list()
                activities = [item for item in modern if item.type_name == "FIT_TYPE_4" and item.size > 0]
                if activities:
                    activities.sort(key=lambda item: (item.page_id or 0, item.file_id.key), reverse=True)
                    return "filesync_v2", activities
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("Garmin modern FileSync unavailable; falling back to legacy directory", exc_info=True)

        directory = parse_directory(await self.async_download_legacy(0, max_bytes=2 * 1024 * 1024))
        activities = [item for item in directory if item.is_activity and item.size > 0]
        activities.sort(key=lambda item: (item.timestamp, item.index), reverse=True)
        return "legacy_directory", activities

    async def async_download_activity(
        self,
        mode: str,
        item: GarminSyncFile | GarminDirectoryEntry,
        *,
        progress: Callable[[int], None] | None = None,
    ) -> GarminDownloadedFile:
        if mode == "filesync_v2":
            if not isinstance(item, GarminSyncFile):
                raise TypeError("modern Garmin activity record type mismatch")
            if not self.transport.supports_service_transfer:
                raise GarminUnsupportedTransport("modern FileSync requires V2 service transfer")
            handle = await self.async_request_modern_file(item)
            compressed = await self.transport.async_download_service_file(handle, progress=progress)
            # Inflation is deliberately left to coordinator/executor code.
            return GarminDownloadedFile(item.file_id.key, compressed, item.size, item.type_name or "FIT_TYPE_4", item.page_id)

        if not isinstance(item, GarminDirectoryEntry):
            raise TypeError("legacy Garmin activity record type mismatch")
        data = await self.async_download_legacy(item.index, max_bytes=min(MAX_LEGACY_FILE_BYTES, max(item.size, 1)))
        return GarminDownloadedFile(item.key, data, item.size, "FIT_TYPE_4", None)

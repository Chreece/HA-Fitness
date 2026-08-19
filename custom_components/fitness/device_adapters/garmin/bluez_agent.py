"""Temporary, address-scoped BlueZ pairing agent for Garmin archive pairing.

BlueZ requires an Agent1 object when the remote device uses numeric-comparison
or other interactive authentication. Home Assistant normally has no default
pairing agent because it is not a desktop pairing wizard. Fitness therefore
registers one only while the user explicitly requests Garmin pairing.

The agent is deliberately narrow:
* it is registered only for the duration of one bounded pairing attempt;
* it accepts requests only for the exact Bluetooth address being paired;
* it rejects PIN/passkey entry requests that Fitness cannot safely answer;
* it is unregistered again immediately after the attempt.
"""

import asyncio
from contextlib import asynccontextmanager
import inspect
import logging

_LOGGER = logging.getLogger(__name__)

_AGENT_PATH = "/com/chreece/fitness/garmin_pairing_agent"
_BLUEZ = "org.bluez"
_AGENT_MANAGER = "org.bluez.AgentManager1"
_AGENT_INTERFACE = "org.bluez.Agent1"
_AGENT_CAPABILITY = "DisplayYesNo"
_AGENT_LOCK = asyncio.Lock()


def _device_suffix(address: str) -> str:
    return "/dev_" + str(address).upper().replace(":", "_")


def _message_error(reply) -> str:
    name = str(getattr(reply, "error_name", None) or "D-Bus error")
    body = getattr(reply, "body", None) or []
    detail = str(body[0]) if body else ""
    return f"{name}: {detail}" if detail else name


def _build_agent(address: str):
    """Build the dbus-fast Agent1 lazily so unit tests need no D-Bus package."""
    from dbus_fast import DBusError
    from dbus_fast.service import ServiceInterface, method

    expected_suffix = _device_suffix(address).upper()

    class FitnessGarminPairingAgent(ServiceInterface):
        def __init__(self):
            super().__init__(_AGENT_INTERFACE)

        def _ensure_target(self, device: str) -> None:
            if not str(device).upper().endswith(expected_suffix):
                _LOGGER.warning(
                    "Rejecting Bluetooth pairing-agent request for non-target device %s while pairing %s",
                    device,
                    address,
                )
                raise DBusError(
                    "org.bluez.Error.Rejected",
                    "Fitness pairing agent is scoped to one explicitly selected device",
                )

        @method()
        def Release(self):
            _LOGGER.debug("BlueZ released temporary Fitness Garmin pairing agent")

        @method()
        def RequestPinCode(self, device: "o") -> "s":
            self._ensure_target(device)
            raise DBusError(
                "org.bluez.Error.Rejected",
                "Fitness cannot safely provide a PIN code for this pairing method",
            )

        @method()
        def DisplayPinCode(self, device: "o", pincode: "s"):
            self._ensure_target(device)
            _LOGGER.info(
                "Garmin pairing PIN displayed by BlueZ for %s: %s",
                address,
                pincode,
            )

        @method()
        def RequestPasskey(self, device: "o") -> "u":
            self._ensure_target(device)
            raise DBusError(
                "org.bluez.Error.Rejected",
                "Fitness cannot safely invent a Bluetooth passkey",
            )

        @method()
        def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
            self._ensure_target(device)
            _LOGGER.info(
                "Garmin pairing passkey displayed by BlueZ for %s: %06d (entered=%d)",
                address,
                int(passkey),
                int(entered),
            )

        @method()
        def RequestConfirmation(self, device: "o", passkey: "u"):
            self._ensure_target(device)
            # This method is reached only while the user has explicitly started
            # one Garmin pairing attempt from Fitness. Confirm the local half of
            # numeric comparison for that exact address; the watch still controls
            # and can reject its own half of the exchange.
            _LOGGER.info(
                "Garmin pairing numeric confirmation accepted for %s (passkey %06d)",
                address,
                int(passkey),
            )

        @method()
        def RequestAuthorization(self, device: "o"):
            self._ensure_target(device)
            _LOGGER.info("Garmin pairing authorization accepted for %s", address)

        @method()
        def AuthorizeService(self, device: "o", uuid: "s"):
            self._ensure_target(device)
            _LOGGER.debug(
                "Garmin pairing service authorization accepted for %s (%s)",
                address,
                uuid,
            )

        @method()
        def Cancel(self):
            _LOGGER.debug("BlueZ canceled temporary Fitness Garmin pairing request")

    return FitnessGarminPairingAgent()


async def _call_agent_manager(bus, member: str, *, signature: str, body: list) -> None:
    from dbus_fast import Message, MessageType

    reply = await bus.call(
        Message(
            destination=_BLUEZ,
            path="/org/bluez",
            interface=_AGENT_MANAGER,
            member=member,
            signature=signature,
            body=body,
        )
    )
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"BlueZ {member} failed: {_message_error(reply)}")


async def _disconnect_bus(bus) -> None:
    try:
        result = bus.disconnect()
        if inspect.isawaitable(result):
            await result
    except Exception:
        _LOGGER.debug("Failed to disconnect temporary BlueZ agent bus", exc_info=True)


async def async_bluez_device_pairing_state(device_path: str) -> tuple[bool, bool, bool]:
    """Return BlueZ Paired/Bonded/Trusted for one known local device path.

    This is intentionally read-only. It lets the Garmin adapter distinguish a
    first-time provisioning connection from an already bonded archive session
    without calling Pair() again on every background sync.
    """
    if not str(device_path).startswith("/org/bluez/"):
        return False, False, False
    try:
        from dbus_fast import BusType, Message, MessageType
        from dbus_fast.aio import MessageBus
    except ImportError:
        return False, False, False

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await bus.call(
            Message(
                destination=_BLUEZ,
                path=str(device_path),
                interface="org.freedesktop.DBus.Properties",
                member="GetAll",
                signature="s",
                body=["org.bluez.Device1"],
            )
        )
        if reply.message_type == MessageType.ERROR:
            _LOGGER.debug(
                "Unable to read BlueZ pairing state for %s: %s",
                device_path,
                _message_error(reply),
            )
            return False, False, False
        props = reply.body[0] if reply.body else {}

        def _value(name: str) -> bool:
            value = props.get(name) if isinstance(props, dict) else None
            return bool(getattr(value, "value", value))

        return _value("Paired"), _value("Bonded"), _value("Trusted")
    finally:
        await _disconnect_bus(bus)


@asynccontextmanager
async def temporary_bluez_pairing_agent(address: str, *, enabled: bool):
    """Register one temporary default BlueZ agent for an explicit local pairing.

    A separate default agent is required because Bleak performs Device1.Pair()
    on its own D-Bus connection. BlueZ associates an application-specific agent
    with the D-Bus application that triggered Pair(); making this narrowly scoped
    agent the temporary default lets the Bleak connection use it too.
    """
    if not enabled:
        yield
        return

    async with _AGENT_LOCK:
        try:
            from dbus_fast import BusType
            from dbus_fast.aio import MessageBus
        except ImportError as err:
            raise RuntimeError(
                "Home Assistant's BlueZ D-Bus client library (dbus-fast) is unavailable"
            ) from err

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        agent = _build_agent(address)
        registered = False
        bus.export(_AGENT_PATH, agent)
        try:
            await _call_agent_manager(
                bus,
                "RegisterAgent",
                signature="os",
                body=[_AGENT_PATH, _AGENT_CAPABILITY],
            )
            registered = True
            await _call_agent_manager(
                bus,
                "RequestDefaultAgent",
                signature="o",
                body=[_AGENT_PATH],
            )
            _LOGGER.info(
                "Temporary address-scoped BlueZ pairing agent active for %s",
                address,
            )
            yield
        finally:
            if registered:
                try:
                    await _call_agent_manager(
                        bus,
                        "UnregisterAgent",
                        signature="o",
                        body=[_AGENT_PATH],
                    )
                except Exception:
                    _LOGGER.debug(
                        "Failed to unregister temporary BlueZ pairing agent",
                        exc_info=True,
                    )
            try:
                bus.unexport(_AGENT_PATH, agent)
            except Exception:
                _LOGGER.debug("Failed to unexport temporary BlueZ pairing agent", exc_info=True)
            await _disconnect_bus(bus)
            _LOGGER.debug(
                "Temporary BlueZ pairing agent removed for %s",
                address,
            )

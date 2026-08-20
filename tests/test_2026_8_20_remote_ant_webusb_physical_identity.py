from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text(encoding="utf-8")
ANT_ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text(encoding="utf-8")
ANT_REMOTE = (ROOT / "custom_components/fitness/live/antplus_core/remote.py").read_text(encoding="utf-8")
SWITCH = (ROOT / "custom_components/fitness/switch.py").read_text(encoding="utf-8")
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text(encoding="utf-8")
DOC = (ROOT / "docs/REMOTE_GATEWAY_PROTOCOL.md").read_text(encoding="utf-8")


def test_remote_ant_ui_reads_opened_from_the_real_usb_device_and_keeps_status_channels_separate():
    status = JS[JS.index("  _renderRemoteGatewayStatus("):JS.index("  async _pairRemoteBleDevice()")]
    assert "this._remoteAntDevice?.device?.opened" in status
    assert "this._remoteAntDevice?.opened" not in status
    assert 'target === "ant"' in status
    assert "this._remoteAntStatusMessage" in status
    assert "this._remoteBleStatusMessage" in status
    assert 'this._renderRemoteGatewayStatus(l.remote_ant_connecting, "ant")' in JS
    assert 'this._renderRemoteGatewayStatus(l.remote_failed, "ant")' in JS


def test_webusb_reports_full_physical_usb_identity_and_uses_backend_canonical_adapter_key_for_packets():
    connect = JS[JS.index("  async _connectRemoteAntUsb("):JS.index("  async _reconnectRemoteAntUsb()")]
    for field in (
        "antplus_vendor_id",
        "antplus_product_id",
        "antplus_serial_number",
        "antplus_manufacturer",
        "antplus_product",
    ):
        assert field in connect
    assert "device.serialNumber" in connect
    assert "device.manufacturerName" in connect
    assert "device.productName" in connect
    assert "antStatus?.adapter_id" in connect
    read_loop = JS[JS.index("  async _remoteAntReadLoop("):JS.index("  _suspendRemoteGatewaysForNavigation()")]
    assert "record.adapterId" in read_loop
    assert "adapter_id:String(record.adapterId" in read_loop


def test_remote_ant_status_materializes_canonical_ant_usb_adapter_not_gateway_placeholder():
    status = REMOTE[REMOTE.index('vol.Required("type"): "fitness/remote_gateway/status"'):REMOTE.index("async def _async_cleanup_legacy_local_cast_tokens")]
    assert "AntUsbAdapter(" in status
    assert 'vid=vid' in status and 'pid=pid' in status
    assert 'serial=str(msg.get("antplus_serial_number")' in status
    assert '"adapter_id": adapter.stable_key' in status
    assert '"capture_states": ({adapter.stable_key: True}' in status
    assert '"authoritative": True' in status
    assert '"vendor_id"' not in status

    hello = REMOTE[REMOTE.index("async def websocket_remote_gateway_hello"):REMOTE.index('vol.Required("type"): "fitness/remote_gateway/ble_device"')]
    assert '"adapters": []' in hello
    assert 'f"webusb:{gateway_id}"' not in hello


def test_ant_manager_treats_explicit_gateway_status_as_authoritative_route_presence():
    assert "remove_missing_immediately: bool = False" in ANT_ADAPTER
    assert "if remove_missing_immediately:" in ANT_ADAPTER
    assert "record.remote_gateways.pop(gateway_id, None)" in ANT_ADAPTER
    status_handler = ANT_REMOTE[ANT_REMOTE.index("    def handle_gateway_status"):ANT_REMOTE.index("    def handle_control_result")]
    assert 'remove_missing_immediately=bool(data.get("authoritative", False))' in status_handler


def test_remote_only_ant_receiver_controls_do_not_pretend_to_control_browser_usb():
    assert 'self.runtime.receiver_management_scope(self.transport, self.receiver_id) != "fitness_owned"' in SWITCH
    assert 'self.runtime.receiver_management_scope(self.transport, self.receiver_id) != "fitness_owned"' in BUTTON
    assert "return bool(record.capture_enabled)" in SWITCH


def test_remote_gateway_documentation_describes_host_independent_ant_usb_identity():
    assert "0FCF:1008:123" in DOC
    assert "antplus_serial_number" in DOC
    assert "same host-independent physical key" in DOC
    assert "does **not** create a physical ANT adapter" in DOC

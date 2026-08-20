from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_backend_options_flow_keeps_explicit_profile_language_across_main_menu_restart():
    assert 'this._language = String(language || this._hass?.language || "en")' in JS
    assert 'language:this._language' in JS
    restart = JS[JS.index("  async _restartOptionsFlow() {"):JS.index("  async _saveAndReturnToMenu() {")]
    assert 'language:this._language' in restart


def test_backend_flow_prefers_requested_fitness_language_over_ha_ui_language():
    localize = JS[JS.index("  _localize(key, fallback"):JS.index("  _flowNamespace()")]
    assert 'let value = this._flowTranslations' in localize
    assert 'const requested = String(this._language || "en")' in localize
    assert 'if (requested === ui)' in localize


def test_browser_ble_reads_standard_device_information_identity():
    assert 'FITNESS_REMOTE_BLE_DEVICE_INFO_SERVICE' in JS
    assert '"00002a25-0000-1000-8000-00805f9b34fb":"serial_number"' in JS
    assert '"00002a29-0000-1000-8000-00805f9b34fb":"manufacturer"' in JS
    assert 'const optionalServices = await this._remoteBleRequestedServices();' in JS
    assert 'optionalServices,' in JS
    assert 'remote_ble_optional_services' in JS
    assert 'FITNESS_REMOTE_BLE_BATTERY_SERVICE' in JS
    assert 'FITNESS_REMOTE_BLE_BATTERY_CHARACTERISTIC' in JS
    assert 'identity,' in JS


def test_remote_browser_route_aliases_to_existing_physical_sensor_and_assigns_profile():
    assert 'vol.Optional("identity", default={}): {str: str}' in REMOTE
    assert 'runtime.find_sensor_for_remote_ble_identity' in REMOTE
    assert 'endpoint_id=endpoint_id' in REMOTE
    assert 'cycplus_m1_name_identity' in REMOTE
    assert 'fitness_physical_identity' in RUNTIME
    assert 'exact_physical_route_identity' in RUNTIME
    assert 'runtime.endpoint_aliases[endpoint_id] = sensor.sensor_id' in REMOTE
    assert 'runtime.enrich_sensor_capabilities' in REMOTE
    assert 'await _async_assign_sensor_to_profile(self.hass, runtime, entry, canonical_sensor_id)' in REMOTE
    assert 'def find_sensor_for_remote_ble_identity' in RUNTIME
    assert 'server-derived exact route identity is strongest' in RUNTIME
    assert 'catalog_product_id' in RUNTIME


def test_disconnecting_browser_alias_does_not_disable_an_existing_local_ble_route():
    assert 'browser_endpoint_id' in REMOTE
    assert 'other_browser_route_active' in REMOTE
    assert 'endpoint.endpoint_id == browser_endpoint_id' in REMOTE
    assert 'and not other_browser_route_active' in REMOTE

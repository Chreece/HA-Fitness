from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
FRONTEND = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
DASH = (FIT / "dashboard.py").read_text(encoding="utf-8")


def _method(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}") if f"    def {name}" in source else source.index(f"  async {name}")
    end = source.index(next_name, start)
    return source[start:end]


def test_every_backend_flow_transition_shows_immediate_visual_working_feedback():
    submit = FRONTEND[FRONTEND.index("  async _submit(data) {"):FRONTEND.index("  async _refreshProgress()", FRONTEND.index("  async _submit(data) {"))]
    assert "_showOperationBusy(" in submit
    assert 'Object.prototype.hasOwnProperty.call(data, "next_step_id")' in submit
    assert "settings_opening" in submit
    assert ".flow-operation-indicator" in FRONTEND
    assert "setInterval(" not in submit


def test_main_menu_never_saves_form_selections_implicitly():
    start = FRONTEND.index("  async _saveAndReturnToMenu() {")
    end = FRONTEND.index("  _renderLoading()", start)
    block = FRONTEND[start:end]
    assert "await this._submit(this._formData)" not in block
    assert "settings_changes_not_saved" in block
    assert "await this._restartOptionsFlow()" in block
    form = FRONTEND[FRONTEND.index('    if (type === "form") {'):FRONTEND.index('    if (type === "create_entry") {')]
    assert "this._formDirty" in form
    assert 'querySelector("#flow-submit")' in form


def test_save_button_wraps_without_clipping_on_narrow_settings_views():
    assert ".flow-actions>button{flex:0 0 auto;align-self:center;height:auto;min-width:118px;max-width:min(220px,100%)}" in FRONTEND
    assert ".flow-actions{display:flex;justify-content:flex-end;align-items:center;align-self:stretch;gap:8px;margin-top:auto;position:sticky" in FRONTEND


def test_account_selector_centers_selected_account_across_whole_control():
    assert ".profile-assign{display:flex;position:relative" in FRONTEND
    assert ".profile-assign ha-icon{position:absolute;left:8px" in FRONTEND
    assert "padding:0 28px" in FRONTEND
    assert "text-align-last:center" in FRONTEND


def test_restored_exact_local_route_can_merge_same_physical_device_safely():
    block = RUNTIME[RUNTIME.index("    def _consolidate_restored_exact_physical_identities"):RUNTIME.index("    def _cleanup_persisted_sensor_alias_devices")]
    assert 'keys.add(("ble_address", address))' in block
    assert 'keys.add(("gatt_serial", serial))' in block
    assert "canonical_keys.intersection(duplicate_keys)" in block
    assert '"restored_exact_local_route_identity"' in block
    # The short CYCPLUS physical token alone must still not merge two local units.
    assert "if not canonical_keys.intersection(duplicate_keys):" in block


def test_registry_cleanup_uses_captured_device_id_and_own_identifiers():
    merge = RUNTIME[RUNTIME.index("    def _merge_physical_sensors"):RUNTIME.index("    def _schedule_merged_registry_cleanup")]
    assert "secondary_device_id = self._sensor_device_ids.get(secondary.sensor_id)" in merge
    assert "_schedule_merged_registry_cleanup(secondary.sensor_id, secondary_device_id)" in merge
    cleanup = RUNTIME[RUNTIME.index("    def _cleanup_persisted_sensor_alias_devices"):RUNTIME.index("    def _select_merge_primary")]
    assert "identifier_owner" in cleanup
    assert "canonical_device_ids" in cleanup
    assert "device_registry.async_remove_device" in cleanup


def test_frontend_cache_revision_85_matches_backend():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASH


def test_mobile_backend_settings_use_viewport_and_compact_nonsticky_header():
    assert 'backendFlowModal ? "backend-flow-backdrop" : "card-picker-preview-backdrop"' in FRONTEND
    assert 'style?.setProperty("--modal-top", "4px")' in FRONTEND
    assert '.backend-flow-backdrop .backend-flow-modal{width:100%!important;height:calc(100dvh' in FRONTEND
    flow_style = FRONTEND[FRONTEND.index('class FitnessBackendFlow'):FRONTEND.index('if (!customElements.get("fitness-backend-flow")')]
    assert '.flow-mobile-description{display:none' in flow_style
    assert '.flow-head p{display:none!important}' in flow_style
    assert 'position:relative!important' in flow_style
    assert '.flow-actions{display:flex;justify-content:flex-end;align-items:center;align-self:stretch' in flow_style
    assert 'position:sticky;bottom:-15px' in flow_style
    assert '@media(max-width:620px){.flow-body{padding:8px 10px max(8px,env(safe-area-inset-bottom))}.flow-actions{bottom:-8px' in flow_style


def test_local_bluetooth_connection_identity_merges_offline_archive_and_live_surfaces():
    info = RUNTIME[RUNTIME.index("    def sensor_device_info"):RUNTIME.index("    def sensor_identity")]
    assert 'connections: set[tuple[str, str]] = set()' in info
    assert 'connections.add(("bluetooth", address))' in info
    assert 'not _browser_ble_endpoint(endpoint)' in info
    cleanup = RUNTIME[RUNTIME.index("    def _cleanup_persisted_sensor_alias_devices"):RUNTIME.index("    def _select_merge_primary")]
    assert "connection_owner" in cleanup
    assert "device.connections" in cleanup
    assert 'startswith("endpoint:bluetooth:")' in cleanup
    ensure = RUNTIME[RUNTIME.index("    def ensure_sensor_device"):RUNTIME.index("    def request_hub_reload")]
    assert 'kwargs["connections"] = set(info["connections"])' in ensure
    assert 'tuple(sorted(info.get("connections") or set()))' in ensure

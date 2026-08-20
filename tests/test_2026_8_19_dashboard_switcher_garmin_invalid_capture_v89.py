from pathlib import Path

ROOT = Path(__file__).parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()


def test_compact_dashboard_switcher_only_exists_for_multiple_dashboards():
    assert 'dashboardRows.length > 1' in JS
    assert 'class="dashboard-switcher"' in JS
    assert 'id="dashboard-prev"' in JS
    assert 'id="dashboard-current"' in JS
    assert 'id="dashboard-next"' in JS
    assert 'await this._manageDashboard("select", dashboardId)' in JS
    assert '.dashboard-switcher{' in JS
    assert 'max-width:min(520px,calc(100% - 18px))' in JS


def test_dashboard_switcher_remains_outside_auto_hidden_toolbar_and_is_tv_navigable():
    assert 'class="dashboard-browser-row">${dashboardNavigator}' in JS
    assert 'class="tv-toolbar' in JS
    assert 'const dashboardSwitcher = this.shadowRoot?.querySelector(".dashboard-switcher")' in JS
    assert 'return "dashboard-switcher"' in JS
    assert ':host([toolbar-hidden]) .dashboard-switcher' in JS


def test_add_dashboard_copy_no_longer_duplicates_plus_icon():
    assert '"add_dashboard":"+ Dashboard"' not in DASH
    assert '"add_dashboard":"Dashboard"' in DASH
    assert '"add_dashboard":"Πίνακας"' in DASH
    assert '<ha-icon icon="mdi:plus"></ha-icon><span>${_fitnessEscape(l.add_dashboard)}</span>' in JS


def test_grid_uses_measured_masonry_gap_without_terminal_row_math():
    assert 'const skyline = Array(packUnits).fill(0)' in JS
    assert 'const packUnits = 200' in JS
    assert 'const gap = FITNESS_TV_CAST_RECEIVER ? 6 :' in JS
    assert 'const totalHeight = placed.length ? Math.max(0, ...skyline) - gap : 0;' in JS


def test_invalid_garmin_payloads_are_preserved_and_probed_privately():
    assert 'INVALID_CAPTURE_DIRNAME = "fitness_garmin_invalid"' in COORD
    assert 'MAX_INVALID_CAPTURE_FILES = 8' in COORD
    assert 'MAX_INVALID_CAPTURE_BYTES = 64 * 1024 * 1024' in COORD
    assert 'self.hass.config.path(".storage", INVALID_CAPTURE_DIRNAME)' in COORD
    assert '"raw_head_hex"' in COORD
    assert '"fit_declared_data_size"' in COORD
    assert '"capture_token": capture.get("token")' in COORD


def test_garmin_full_sync_accepts_standard_deflate_wrappers_only_when_they_reveal_fit():
    assert '("zlib", zlib.MAX_WBITS)' in COORD
    assert '("gzip", zlib.MAX_WBITS | 16)' in COORD
    assert '("raw-deflate", -zlib.MAX_WBITS)' in COORD
    assert 'if _looks_like_fit(inflated):' in COORD
    assert 'Garmin payload is not a raw/zlib/gzip/raw-deflate FIT container' in COORD


def test_frontend_cache_revision_is_v89():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert '?v=unreleased-110' in DASH
    assert '"frontend_version": "unreleased-110"' in DASH


def test_existing_invalid_without_capture_is_reprobed_after_upgrade() -> None:
    assert 'if kind == "unsupported":' in COORD
    assert 'if kind != "invalid":' in COORD
    assert 'int(cached.get("decoder_revision") or 0) < GARMIN_PAYLOAD_DECODER_REVISION' in COORD
    assert 'not cached.get("capture_token")' in COORD
    assert '_catalog_item_fingerprint(item)' in COORD
    assert 'uncached_items = [item for item in catalog if _needs_download(item)]' in COORD

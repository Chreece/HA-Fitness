from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text(encoding="utf-8")
BASE = (ROOT / "custom_components/fitness/music/base.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")


def test_search_results_normalize_rich_music_metadata_across_adapters():
    for source in (MA, BASE, YTDLP):
        assert '"album"' in source
        assert '"year"' in source
        assert '"duration"' in source
        assert '"thumbnail"' in source
    assert '"artist": artist_value' in MA
    assert '"album": album_value' in MA
    assert '"year": year_value' in MA
    assert '"provider_name": provider_label' in MA
    assert '"provider_origin": provider_origin or self.info.name' in MA
    assert 'provider_origin = " · ".join(' in MA


def test_music_assistant_origin_distinguishes_inner_provider():
    assert 'value for value in (self.info.name, provider_label) if value' in MA
    assert 'provider_origin:selectedMetadata.provider_origin' in FRONTEND
    assert '`Music Assistant · ${selectedMetadata.provider_name}`' in FRONTEND
    assert '_mediaProviderLabel(value = {})' in FRONTEND


def test_search_result_cards_show_artwork_and_metadata_lines():
    assert 'class="media-thumb"' in FRONTEND
    assert '_mediaResultMetadata(item = {})' in FRONTEND
    assert 'metadata.artist, metadata.album' in FRONTEND
    assert 'if (metadata.year) secondary.push(metadata.year)' in FRONTEND
    assert 'if (metadata.duration > 0) secondary.push(this._formatMediaTime(metadata.duration))' in FRONTEND
    assert 'if (provider) secondary.push(provider)' in FRONTEND
    assert 'class="media-result-primary"' in FRONTEND
    assert 'class="media-result-secondary"' in FRONTEND


def test_now_playing_uses_same_artist_album_year_provider_metadata():
    assert 'metadata.artist, metadata.album, metadata.year, providerLabel, metadata.details' in FRONTEND
    for key in ('"album"', '"year"', '"provider"', '"provider_name"', '"provider_origin"'):
        assert key in TV
    assert 'replay_metadata = {' in TV
    assert '"provider_origin",' in TV


def test_progress_bar_aligns_to_song_column_and_shows_total_duration():
    assert '<div class="media-progress-wrap">' in FRONTEND
    assert '<input id="media-progress"' in FRONTEND
    assert '<div class="media-time-row"><span id="media-current">0:00</span><span id="media-remaining">—</span></div>' in FRONTEND
    assert '.media-progress-wrap{display:grid;grid-template-columns:minmax(0,1fr)' in FRONTEND
    assert '.media-time-row{display:flex;align-items:center;justify-content:space-between' in FRONTEND
    assert '? this._formatMediaTime(duration)' in FRONTEND
    assert 'aria-valuetext", duration > 0' in FRONTEND


def test_frontend_revision_is_v76():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-85"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-85"' in DASHBOARD

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_workout_viewer_pages_older_history_instead_of_stopping_at_initial_rows():
    assert 'this._historyPageSize=60' in FRONTEND
    assert 'if(!reset&&this._historyNextCursor)msg.cursor=this._historyNextCursor' in FRONTEND
    assert 'async _selectOlder()' in FRONTEND
    assert 'if(!this._historyHasMore)return' in FRONTEND
    assert 'const loaded=await this._loadWorkouts(false)' in FRONTEND
    assert "idx>=this._rows.length-1&&!this._historyHasMore?'disabled':''" in FRONTEND
    assert 'limit:500' not in FRONTEND[FRONTEND.index('class FitnessWorkoutCard'):FRONTEND.index('class FitnessSleepRecoveryCard')]


def test_workout_browser_defaults_to_all_workouts_not_calendar_only():
    browser = FRONTEND[FRONTEND.index('class FitnessWorkoutBrowserCard'):FRONTEND.index('class FitnessBodyCompositionCard')]
    assert 'this._view="all"' in browser
    assert 'data-view="all"' in browser
    assert 'data-view="calendar"' in browser
    assert 'const visibleRows=this._view==="calendar"?' in browser
    assert ':this._rows;' in browser
    assert 'data-load-older' in browser
    assert 'this._total!=null?' in browser


def test_old_browser_selection_carries_loaded_workout_data_back_to_map_viewer():
    browser = FRONTEND[FRONTEND.index('class FitnessWorkoutBrowserCard'):FRONTEND.index('class FitnessBodyCompositionCard')]
    viewer = FRONTEND[FRONTEND.index('class FitnessWorkoutCard'):FRONTEND.index('class FitnessSleepRecoveryCard')]
    assert 'workout,workouts:this._rows.slice(),next_cursor:this._nextCursor,has_more:this._hasMore,total:this._total' in browser
    assert 'detail:this._selectionDetail(el.dataset.uid)' in browser
    assert '_acceptBrowserSelection(detail)' in viewer
    assert 'const rows=Array.isArray(detail?.workouts)?detail.workouts' in viewer
    assert 'this._mergeWorkoutRows(rows)' in viewer


def test_workout_browser_all_history_labels_cover_supported_languages():
    browser = FRONTEND[FRONTEND.index('class FitnessWorkoutBrowserCard'):FRONTEND.index('class FitnessBodyCompositionCard')]
    for language in ("en", "el", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"):
        assert f'{language}:["' in browser
    assert '"All workouts","Calendar"' in browser
    assert '"Όλες οι προπονήσεις","Ημερολόγιο"' in browser

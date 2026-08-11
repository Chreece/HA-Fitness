from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
DETAILS = (ROOT / "custom_components/fitness/evaluation_details.py").read_text(encoding="utf-8")


def test_internal_scientific_keys_are_not_exposed_by_grouped_evaluation():
    assert 'attrs = {"evaluation_scope": m}' not in SENSOR
    grouped_section = SENSOR[SENSOR.index('grouped = {'):SENSOR.index('if grouped:')]
    assert '"research_reference"' not in grouped_section
    assert '"evidence_level"' not in grouped_section


def test_scientific_evaluation_has_human_facing_metadata():
    assert 'evaluation_user_details(' in SENSOR
    for phrase in (
        '"Scientific basis"',
        '"Επιστημονική βάση"',
        '"Formula"',
        '"Τύπος"',
        '"Data used"',
        '"Δεδομένα που χρησιμοποιήθηκαν"',
        '"What this means"',
        '"Τι σημαίνει"',
        '"Why this is useful"',
        '"Γιατί είναι χρήσιμο"',
    ):
        assert phrase in DETAILS


def test_scientific_basis_uses_real_reference_titles():
    assert 'REFERENCES' in DETAILS
    assert 'study_citation' in DETAILS
    assert 'PMID' in DETAILS


def test_data_used_is_dynamic_from_actual_entities():
    assert 'self.hass.states.get(entity_id)' in SENSOR
    assert 'provider.get("vo2max_entity")' in SENSOR
    assert 'latest_sleep.field_sources' in SENSOR
    assert 'latest_workout.sources' in SENSOR

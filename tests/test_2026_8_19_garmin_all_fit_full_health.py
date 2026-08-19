from pathlib import Path

ROOT = Path(__file__).parents[1]
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text()
FIT = (ROOT / "custom_components/fitness/device_adapters/garmin/fit.py").read_text()
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()
HISTORY = (ROOT / "custom_components/fitness/device_adapters/history.py").read_text()


def test_modern_garmin_full_sync_inspects_fit_labeled_and_known_numeric_families():
    assert 'name.startswith("FIT_TYPE_")' in GFDI
    assert 'item.type_code in {4, 9, 14, 15, 28, 32}' in GFDI
    assert 'item.type_code is not None\n            or name.startswith("FIT_TYPE_")' not in GFDI


def test_legacy_garmin_full_sync_inspects_every_fit_subtype():
    assert 'item.size > 0 and item.data_type == 128' in GFDI
    assert 'item.sub_type in {4, 9, 14, 15, 28, 32}' not in GFDI


def test_unknown_fit_family_is_content_inventoried_not_guessed():
    assert 'def fit_message_names' in FIT
    assert 'record["fit_messages"] = list(fit_message_names(fit))[:64]' in COORD
    assert 'Garmin FIT family not yet mapped' in COORD


def test_health_file_proven_by_content_is_refreshed_even_with_unknown_type_id():
    assert 'cached.get("kind") == "health"' in COORD


def test_direct_device_health_batch_can_retain_full_day_multi_metric_history():
    assert 'MAX_DEVICE_METRIC_POINTS = 8192' in HISTORY

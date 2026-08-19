from pathlib import Path
ROOT=Path(__file__).parents[1]
INIT=(ROOT/"custom_components/fitness/__init__.py").read_text()
SERV=(ROOT/"custom_components/fitness/services.yaml").read_text()
ARCH=(ROOT/"custom_components/fitness/device_archives.py").read_text()
GAR=(ROOT/"custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()
CYC=(ROOT/"custom_components/fitness/device_adapters/cycplus_m1.py").read_text()

def test_fit_cleanup_has_explicit_ownership_scope():
    assert 'ownership", default="profile"' in INIT
    assert "All Fitness-owned FIT caches" in SERV
    assert 'ownership: str = "profile"' in ARCH

def test_profile_cleanup_uses_imported_profile_ownership_and_never_device_files():
    for source in (GAR, CYC):
        assert 'profile_id in {str(value) for value in record.get("imported_profiles") or []}' in source
        assert 'ownership == "all_fitness_owned"' in source
        assert "eligible_keys" in source
        assert "never delete files on the device" not in source.lower() or "delete" not in source[source.find("async_clear_fit_cache"):source.find("async_clear_fit_cache")+1000].lower()

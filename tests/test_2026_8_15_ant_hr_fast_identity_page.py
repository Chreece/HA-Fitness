"""Source-level guards for slow ANT background identity latency."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()


def test_serial_identity_pages_do_not_wait_two_background_cycles():
    block = RECEIVER.split("def _observe_metadata_candidate", 1)[1].split("def ", 1)[0]
    assert "serial_identity_page" in block
    assert "DEVICE_TYPE_HEART_RATE and page == 2" in block
    assert "BSC_IDENTITY_PAGE_PROFILES and page == 2" in block
    assert "COMMON_IDENTITY_PAGE_PROFILES and page == 0x51" in block
    assert "1 if serial_identity_page else IDENTITY_CONFIRM_OBSERVATIONS" in block

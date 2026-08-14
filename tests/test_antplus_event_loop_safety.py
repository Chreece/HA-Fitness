from pathlib import Path

ANTPLUS = Path('custom_components/fitness/live/antplus.py').read_text()
RECEIVER = Path('custom_components/fitness/live/antplus_core/receiver.py').read_text()


def test_ant_receiver_capture_control_runs_in_executor():
    assert 'await self.hass.async_add_executor_job(self.receiver.enable_capture)' in ANTPLUS
    assert 'await self.hass.async_add_executor_job(self.receiver.disable_capture)' in ANTPLUS
    assert '\n            self.receiver.enable_capture()' not in ANTPLUS
    assert '\n            self.receiver.disable_capture()' not in ANTPLUS


def test_usb_presence_probe_remains_sync_worker_helper():
    # Sync sysfs probing is fine as long as its callers are executor-backed.
    assert 'def _local_usb_present(self)' in RECEIVER
    assert 'idVendor").read_text()' in RECEIVER
    assert 'idProduct").read_text()' in RECEIVER

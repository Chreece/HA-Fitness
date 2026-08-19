from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_miband7_is_registered_on_read_only_keyed_transport() -> None:
    protocol = read("custom_components/fitness/device_adapters/huami_keyed/protocol.py")
    adapters = read("custom_components/fitness/device_adapters/huami_keyed/adapters.py")
    coordinator = read("custom_components/fitness/device_adapters/huami_keyed/coordinator.py")
    assert '"xiaomi_miband7"' in protocol
    assert "MiBand7Coordinator" in adapters
    assert 'MIBAND7_ARCHIVE_ADAPTER = _spec("xiaomi_miband7")' in adapters
    # Non-destructive pairing remains a hard requirement for Band 7 too.
    assert "AUTH_SEND_KEY" not in coordinator
    assert 'fields=("auth_key",)' in coordinator


def test_modern_xiaomi_catalog_covers_missing_generations() -> None:
    catalog = json.loads(read("custom_components/fitness/live/device_catalog.json"))
    ids = {item["id"] for item in catalog["products"]}
    expected = {
        "xiaomi_miband7",
        "xiaomi_smart_band7_pro",
        "xiaomi_smart_band8",
        "xiaomi_smart_band8_active",
        "xiaomi_smart_band8_pro",
        "xiaomi_smart_band9",
        "xiaomi_smart_band9_active",
        "xiaomi_smart_band9_pro",
        "xiaomi_smart_band10",
        "xiaomi_smart_band10_pro",
    }
    assert expected <= ids


def test_band10_uses_standard_hr_with_guided_repair() -> None:
    adapter = read("custom_components/fitness/device_adapters/xiaomi_hr_broadcast/adapter.py")
    registry = read("custom_components/fitness/device_adapters/registry.py")
    assert 'SERVICE_HR = BASE.format("180d")' in adapter
    assert 'action=ACTION_ENABLE_HR' in adapter
    assert "Settings, then Share HR" in adapter
    assert '"hr_broadcast_active": SERVICE_HR in services' in adapter
    assert "*XIAOMI_HR_BROADCAST_ADAPTERS" in registry

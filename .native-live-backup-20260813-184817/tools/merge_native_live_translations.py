#!/usr/bin/env python3
"""Merge native live-adapter UI strings without replacing existing translations."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "fitness"

CONFIG_STEPS = {
    "live_transports": {
        "title": "Live workout adapters",
        "description": "Choose which native radio transports Fitness should create. These become global Fitness adapter devices and can later be enabled or disabled from the adapter device itself.",
        "data": {
            "bluetooth_fitness_enabled": "Create Bluetooth Fitness adapter",
            "antplus_enabled": "Create ANT+ adapter",
        },
        "data_description": {
            "bluetooth_fitness_enabled": "Use Home Assistant Bluetooth, including compatible Bluetooth proxies, to discover and actively connect to standard fitness sensors.",
            "antplus_enabled": "Use the native HA-ANT+ runtime for local ANT USB adapters and remote ANT+ gateways.",
        },
    },
    "live_devices": {
        "title": "Live workout sensors",
        "description": "Select the physical sensors this Fitness profile may use. Native sensors come from the enabled Bluetooth and ANT+ adapter modules. Optional compatible Home Assistant live devices can also be used.",
        "data": {
            "live_sensor_ids": "Bluetooth / ANT+ fitness sensors",
            "live_device_ids": "Other Home Assistant live devices",
        },
        "data_description": {
            "live_sensor_ids": "Physical sensors discovered by the global Fitness Bluetooth and ANT+ adapters. Metrics from several sensors can be combined in one workout.",
            "live_device_ids": "Optional legacy/provider Home Assistant devices exposing compatible live heart-rate, power, cadence, speed, distance or altitude entities.",
        },
    },
    "assign_live_sensor": {
        "title": "New fitness sensor discovered",
        "description": "{sensor} was discovered. Choose every Fitness user who may use this physical sensor for live workouts.",
        "data": {"fitness_profile_ids": "Fitness users"},
        "data_description": {"fitness_profile_ids": "One physical sensor can be shared by multiple Fitness profiles."},
    },
}

OPTIONS_STEPS = {
    "live_transports": CONFIG_STEPS["live_transports"],
    "live_devices": CONFIG_STEPS["live_devices"],
}

ABORTS = {
    "live_sensor_assigned": "The fitness sensor was assigned successfully.",
    "sensor_unavailable": "The discovered fitness sensor is no longer available.",
    "no_fitness_profiles": "Create a Fitness user before assigning this sensor.",
    "invalid_discovery": "The fitness sensor discovery data was invalid.",
    "adapters_already_configured": "All Fitness live adapters are already configured. Enable or disable them from their adapter devices.",
}
ERRORS = {"select_profile": "Select at least one Fitness user."}


def merge(path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    config = data.setdefault("config", {})
    config.setdefault("step", {}).update(CONFIG_STEPS)
    config.setdefault("abort", {}).update(ABORTS)
    config.setdefault("error", {}).update(ERRORS)
    data.setdefault("options", {}).setdefault("step", {}).update(OPTIONS_STEPS)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


merge(ROOT / "strings.json")
for path in (ROOT / "translations").glob("*.json"):
    merge(path)
print("Merged native live-adapter config-flow strings.")

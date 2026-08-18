# Smart workout devices

HA-Fitness treats a smart workout device as **one physical device with multiple capabilities and transports**. A watch can therefore expose live heart rate, battery, ANT+/Bluetooth routes and a local stored-workout archive without appearing as separate Fitness devices.

## Normal setup

1. Enable the Fitness Bluetooth adapter under **Sensors & Adapters**.
2. Open the Fitness profile that should own the device's stored workouts.
3. Open **Smart workout devices**.
4. Fitness requests one short, bounded Bluetooth discovery sweep and lists detected physical workout-archive devices. Devices can also appear automatically through normal Home Assistant Bluetooth discovery, just like other Fitness sensors.
5. Select the detected physical device. Choose a device type if useful for display and optionally adjust its display model label. These values are **never used to select a protocol backend**.
6. Finish setup. The current Fitness profile becomes the primary owner for stored-workout imports. Existing live-sensor assignment remains independent, so the same physical device can still be shared for live metrics when appropriate.
7. If a vendor requires pairing, follow the vendor-specific instructions shown after setup. Garmin, for example, only needs a one-time Bluetooth bond if the later sync diagnostic reports **Pairing required**.

## Automatic discovery and manual guides

The Smart workout devices page contains both detected physical devices and supported setup guides. For now the manual guided vendor flow includes Garmin. The guide can collect a broad device type such as sport watch or bike computer and an optional model label, but those are setup/display hints only. Actual support is always determined from verified manufacturer/protocol evidence and connected capabilities.

A blank or unfamiliar consumer model name does not make a device unsupported when its protocol capabilities are known.

## Physical-device merging

Fitness merges capabilities into the canonical physical device whenever strong identity evidence exists. Examples:

- a watch first discovered as a Bluetooth heart-rate monitor and later recognized as a local workout archive remains one device;
- a browser Bluetooth route and an autonomous Home Assistant Bluetooth route can merge when they expose the same strong physical identity;
- ANT+ and Bluetooth routes can merge when serial/protocol identity or a conservative data-driven correlation proves they are the same physical unit.

Model names alone are never sufficient merge evidence. Two people can own identical products, so same-name devices remain separate unless stronger identity is available.

Stored-workout ownership is intentionally separate from live workout ownership. A smart device has one primary Fitness profile for local archive imports, while live metrics keep the existing assignment and exclusive active-workout ownership rules.

## Performance and safety rules

Smart device setup is control-plane work and is deliberately bounded:

- opening the page performs at most one short active Bluetooth scan, subject to the Bluetooth provider's cooldown;
- discovery and cache replay never open GATT;
- device/model selectors are bounded in size and length;
- no model probing loops or permanent Bluetooth connections are created;
- actual archive synchronization keeps the adapter-specific hard session, transfer, memory, retry and cleanup limits;
- live-workout BLE ownership always wins over background archive work;
- repeated failures back off instead of continuously waking the Bluetooth stack.

Vendor adapters must remain read-only unless a future feature explicitly documents otherwise. The Garmin adapter does not mark files synced, archive them or delete them.

## Garmin

See [Local Garmin workout synchronization](GARMIN_LOCAL.md) for Garmin-specific pairing, GFDI capability detection, diagnostics and troubleshooting.

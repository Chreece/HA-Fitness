# Native fitness sensors

Fitness can merge ANT+ and Bluetooth representations of the same physical sensor into one Home Assistant device.

## Identity

Identity is accumulated rather than guessed. Numeric protocol identifiers (for example an ANT model number) are retained as disabled diagnostic entities and are not used as the user-facing model. Fitness enriches the physical device as standard ANT common pages and Bluetooth Device Information become available. Supported fields include manufacturer, model, model ID, serial number, hardware revision and software/firmware revision.

`custom_components/fitness/live/device_catalog.json` contains data-driven manufacturer/product/profile recognition. It is intentionally separate from runtime logic so support can be expanded without adding vendor-specific branches. Automatic ANT+/Bluetooth merging remains conservative: a matching serial or an explicit product-family catalog rule is required; identical names alone never merge devices.

## Information entities

Core live measurements remain normal sensor entities. Additional decoded ANT+ values, ANT identity/profile/control/event capabilities, BLE advertisement fields, GATT services/characteristics and Device Information values are retained as merged detail entities. Diagnostic or high-frequency/advanced fields are disabled by default. When ANT+ and Bluetooth report the same canonical fact, Fitness keeps one entity and exposes the source values as attributes.

Battery is treated as one passive physical value across transports. `Last seen` remains disabled by default and uses five-minute precision to avoid Recorder churn.

## Events and controls

Positively detected semantic protocol events are represented by Home Assistant Event entities. Fitness retains detected control capabilities diagnostically. It does not send guessed ANT+/Bluetooth control payloads: writable controls require a verified encoder, valid range/unit contract and protocol acknowledgement handling before they become actionable.

Bluetooth GATT connect/disconnect is an actionable transport control. Manual connect is unavailable while fresh ANT+ data exists. During a workout, Fitness prefers fresh ANT+ broadcasts; if ANT+ is unavailable/stale and a connectable BLE endpoint exists, Fitness opens GATT automatically **only for the profile that exclusively owns that physical sensor for the workout**. If ANT+ resumes, the same owner hands transport back to ANT+ and BLE GATT is disconnected. Transport handover never changes workout ownership.

## Shared assignments and exclusive workout ownership

A physical sensor may be assigned to multiple Fitness profiles so different people can use the same hardware at different times. Assignment is configuration permission, **not simultaneous measurement sharing**. When a session is armed, an observed free sensor is claimed by the oldest eligible armed session. A claimed physical sensor (including all merged ANT+ and Bluetooth identities) feeds only that profile. Other profiles ignore its packets and remain armed until one of their other free assigned sensors supplies usable measurements; their workout timer does not start from the locked sensor.

Sensor locks deliberately outlive the original owner's stop while any overlapping Fitness session or HR-recovery session is still running. This prevents a still-worn sensor from suddenly being inherited by another person's ongoing workout. Locks are cleared only when the global overlapping workout epoch becomes idle (no armed, active or recovery sessions). The Local Sensors options expose **Sensor assignments**, where one physical sensor can be reassigned to any combination of Fitness profiles after setup.

## Load protection

Radio packets update only the physical entities whose value/provenance changed. Identical packets do not produce Home Assistant state writes. Physical writes and profile live processing are coalesced, while completed-workout sampling remains independently bounded. Repeated BLE advertisements with unchanged structural metadata use a volatile fast path for RSSI/last-seen/availability instead of rebuilding physical identity.

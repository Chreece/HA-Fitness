# Native fitness sensors

Fitness can merge ANT+ and Bluetooth representations of the same physical sensor into one Home Assistant device. It can also represent a supported device workout archive, such as the CYCPLUS M1, without pretending that archive is a live metric source.

## Identity

Identity is accumulated rather than guessed. Numeric protocol identifiers (for example an ANT model number) are retained as disabled diagnostic entities and are not used as the user-facing model. Fitness enriches the physical device as standard ANT common pages and Bluetooth Device Information become available. Supported fields include manufacturer, model, model ID, serial number, hardware revision and software/firmware revision.

`custom_components/fitness/live/device_catalog.json` contains data-driven manufacturer/product/profile recognition. It is intentionally separate from runtime logic so support can be expanded without adding vendor-specific branches. Automatic ANT+/Bluetooth merging remains conservative: a matching serial or an explicit product-family catalog rule is required; identical names alone never merge devices.


### Vendor/product decoder registry

The generic live-telemetry runtime contains no product-specific decode branches. Product
recognition and proprietary advertisement payload definitions are selected from
`custom_components/fitness/live/device_catalog.json`; the generic
`vendor_registry.py` engine validates and executes those definitions.

A non-standard sensor is extended by data, not by adding `if vendor == ...`
logic to `bluetooth.py`, `antplus.py`, `runtime.py`, or the ANT receiver. A
catalog product may reference one or more `decoder_ids`. Decoder definitions
declare the transport/phase, payload source, byte offset/length/encoding,
validation range, metric key and Home Assistant metadata. A decoder is executed
only after the same catalog has positively matched the observed product family.

For example, a proprietary Bluetooth advertisement field is represented
conceptually as:

```json
{
  "id": "product_decoder_v1",
  "transport": "bluetooth",
  "phase": "advertisement",
  "source": {"kind": "manufacturer_data", "id": 12345},
  "fields": [{
    "metric": "battery",
    "offset": 1,
    "length": 1,
    "encoding": "uint_le",
    "valid_min": 0,
    "valid_max": 100
  }]
}
```

The company ID and byte offset therefore live only in the catalog. Standard
Bluetooth SIG and ANT+ profile decoding remains protocol-generic code because
those layouts are standards rather than vendor exceptions. Invalid/missing
decoder definitions are non-fatal: the vendor registry reports consistency
issues and skips unsupported definitions instead of preventing Fitness startup.

A regression audit scans every Python file under `custom_components/fitness/live`
and rejects known vendor/product literals in native runtime code. Provider
adapters under `custom_components/fitness/providers/` are intentionally outside
this rule: Garmin/Strava/Oura/etc. adapters parse those Home Assistant
integrations and are not native ANT+/BLE physical-sensor decoders.

Device archive protocols are a separate boundary: a verified product may have a
small, isolated transfer adapter when its protocol cannot be described as an
advertisement-field decoder. It shares discovery, assignment and physical-device
identity with the generic runtime, but never adds fake live metrics.

## CYCPLUS M1 workout archive

Fitness recognizes the CYCPLUS M1 only when both its `M1_…`/CYCPLUS M1 local name
and documented vendor service are advertised. The device then appears in **Local
Sensors** as an assignable workout-history sensor. Accepting it does not open a
permanent GATT connection: Fitness connects only for an automatic or manual archive
sync and disconnects afterwards. A connectable Home Assistant Bluetooth adapter or
proxy must be in range, and the M1 must be powered on.

The sync reads `filelist.txt` (with `workouts.json` firmware fallback), downloads
every timestamped FIT workout not already checkpointed, verifies FIT framing and
CRC, and imports every completed session through Fitness's canonical workout merge.
The protocol exposes no byte-offset seek command. Fitness therefore resumes safely
at a **file boundary**: completed files remain checkpointed, while an interrupted or
invalid active file is downloaded again from its beginning after automatic
reconnection. Retry delay is bounded and increases after repeated failures. Large
initial archives are processed in batches of at most three files. Fitness closes
the Bluetooth connection between batches, waits before continuing automatically,
and writes each profile history only once per batch so an old device with hundreds
of workouts cannot monopolize Home Assistant's memory, storage or event loop.

FIT transfers, decoded record counts and persisted auxiliary provider payloads
have explicit safety limits. Normalized workout facts remain intact; oversized raw
routes/provenance are downsampled or compacted. Existing installations perform one
automatic compaction of legacy workout-history payloads before accepting new device
imports. Removing the M1 from all profiles cancels the active synchronization, and
Bluetooth cleanup has a timeout so a stuck BlueZ/GATT operation cannot block a Home
Assistant restart indefinitely.

Already decoded workout summaries are kept in the private checkpoint store. If the
same M1 is later assigned to another Fitness profile, that profile can import the
cached workouts without forcing the slow BLE device to resend them. Profile-specific
derived context is calculated from an independent copy, so one person's history
cannot affect another person's imported record.

Enabled diagnostic entities show device number, sync state, attempts/success time,
device/imported/pending file counts, active download, last error and latest workout.
Optional diagnostics expose downloaded bytes, free/total storage, FIT serial,
manufacturer/product, hardware/software version and battery voltage/status. Stable
identity fields also enrich the Home Assistant device registry. **Sync workouts
now** requests an immediate retry; normal synchronization is automatic.

The M1's browser live-measurement route and Home Assistant archive route use
different Bluetooth identifiers and may report different GATT and FIT serial
namespaces. Fitness correlates only the exact hexadecimal number encoded in the
M1 local name, keeps the local/proxy route for automatic reconnection, and treats
the FIT serial and revisions as diagnostics rather than physical DeviceInfo. This
also migrates a previously split browser/archive pair back to one HA device.

Battery percentage is read from the standard Battery Level characteristic when
the M1 connects; it does not depend on the device placing the percentage in its
advertisement. Live metric entities are derived from the connected GATT
characteristics and from successfully decoded samples. Cadence, power, speed or
distance therefore appear when the device actually exposes those measurements;
Fitness does not create unsupported placeholder measurements merely because they
may exist inside completed FIT workouts.

## Information entities

Core live measurements remain normal sensor entities. Additional decoded ANT+ values, ANT identity/profile/control/event capabilities, BLE advertisement fields, GATT services/characteristics and Device Information values are retained as merged detail entities. Diagnostic or high-frequency/advanced fields are disabled by default. When ANT+ and Bluetooth report the same canonical fact, Fitness keeps one entity and exposes the source values as attributes.

Battery is treated as one passive physical value across transports. `Last seen` remains disabled by default and uses five-minute precision to avoid Recorder churn.

## Events and controls

Positively detected semantic protocol events are represented by Home Assistant Event entities. Fitness retains detected control capabilities diagnostically. It does not send guessed ANT+/Bluetooth control payloads: writable controls require a verified encoder, valid range/unit contract and protocol acknowledgement handling before they become actionable.

The adapter **Activate** switch is the only live transport/module control. There are no capture buttons and no manual GATT connect/disconnect buttons. While Bluetooth is enabled, Fitness listens passively through Home Assistant's Bluetooth stack. During a workout, Fitness prefers fresh ANT+ broadcasts; if ANT+ is unavailable/stale and a connectable BLE endpoint exists, Fitness opens GATT automatically **only for the profile that exclusively owns that physical sensor for the workout**. If ANT+ resumes, the same owner hands transport back to ANT+ and BLE GATT is disconnected automatically. Transport handover never changes workout ownership. An archive device may expose a separate one-shot **Sync workouts now** retry action; it does not control the Bluetooth module or keep GATT connected.

## Shared assignments and exclusive workout ownership

A physical sensor may be assigned to multiple Fitness profiles so different people can use the same hardware at different times. Assignment is configuration permission, **not simultaneous measurement sharing**. When a session is armed, an observed free sensor is claimed by the oldest eligible armed session. A claimed physical sensor (including all merged ANT+ and Bluetooth identities) feeds only that profile. Other profiles ignore its packets and remain armed until one of their other free assigned sensors supplies usable measurements; their workout timer does not start from the locked sensor.

Sensor locks deliberately outlive the original owner's stop while any overlapping Fitness session or HR-recovery session is still running. This prevents a still-worn sensor from suddenly being inherited by another person's ongoing workout. Locks are cleared only when the global overlapping workout epoch becomes idle (no armed, active or recovery sessions). The Local Sensors options expose **Sensor assignments**, where one physical sensor can be reassigned to any combination of Fitness profiles after setup.

## Load protection

Radio packets update only the physical entities whose value/provenance changed. Identical packets do not produce Home Assistant state writes. Physical writes and profile live processing are coalesced, while completed-workout sampling remains independently bounded. Repeated BLE advertisements with unchanged structural metadata use a volatile fast path for RSSI/last-seen/availability instead of rebuilding physical identity.

# Direct device health history

HA-Fitness can import longitudinal health history directly from supported local Bluetooth wearables. This path does **not** require FIT files, a phone relay, a vendor cloud account, or Gadgetbridge at runtime.

```text
wearable -> local Bluetooth -> Home Assistant -> HA-Fitness profile history
```

The device adapter owns the vendor/protocol details. The shared Bluetooth transport remains device-neutral and uses Home Assistant's Bluetooth routing/connection management.

## Canonical data that can be imported

Depending on what the physical device exposes, a direct-history adapter may contribute:

- sleep sessions and explicit sleep stages;
- daily steps, distance, calories and active minutes;
- heart rate and daily minimum/maximum heart rate;
- HRV;
- SpO2;
- skin temperature and documented device-state values;
- stress and activity-level history;
- bounded intraday samples as well as compact long-term daily summaries where the device exposes timestamped records.

Adapters only create facts explicitly exposed by the device protocol. Fitness does not infer missing sleep stages or invent measurements merely because another product in the same family supports them.

## Implemented protocol families

### Ultrahuman Ring AIR

Read-only local history uses the Ring AIR recording/index commands. Fitness imports recorded heart rate, HRV, SpO2, separate average/minimum/maximum skin temperature, activity level, steps and stress. Timestamped recordings are retained in a bounded intraday history window while compact daily summaries remain available for long-term trends. Battery, charging state and documented device temperature are also retained when exposed by the Device State characteristic.

The documented recording stream does not provide an explicit sleep-session/stage contract, so this adapter currently does not manufacture sleep from activity records.

### Bangle.js 1 / 2 / 3

Fitness uses the documented Nordic-UART console to retrieve Bangle.js Health records and Recorder files without a vendor cloud. Health records contribute timestamped steps, heart rate and temperature plus explicit light/deep sleep states. Recorder workouts are imported with their recorded metrics and a bounded GPS route when latitude/longitude samples exist. Battery, charging and wear state are retained as device-state history.

### Xiaomi Mi Band 1 / 1A / 1S

Fitness implements the legacy Mi Band activity-history protocol directly. Per-minute records are timestamped from the transfer header and retained as bounded intraday history. Documented activity categories contribute steps, activity intensity, explicit light/deep sleep and not-worn state; battery/charging state and current daily steps are also imported. Missing stages such as REM are never inferred.

### Xiaomi Mi Band 2

Fitness performs non-destructive challenge/response authentication with the legacy Mi Band 2 key and reads retained per-minute activity packets, current daily steps and battery level. Each minute can contribute steps, activity intensity and valid stored heart rate. The raw activity category is retained as context, but Fitness does not currently translate it into sleep stages because the independently documented category-to-sleep mapping is not stable enough to treat as a fact. Fitness never sends the key-initialization command during automatic or manual sync because doing so can replace an existing app pairing. Authentication failures emit a user-action request with recovery steps instead.

### Xiaomi Mi / Smart Band 3–7

Fitness uses the read-only keyed Huami BLE history path for Mi Band 3 and Xiaomi Smart Band 4–7. These devices require the 16-byte device authentication key already associated with their vendor pairing. Fitness never installs or replaces that key. When the key is missing or rejected, Home Assistant creates a fixable Repair with step-by-step instructions and a password-style 32-hex-character field; completing the Repair retries the full sync immediately. The adapter imports bounded per-minute steps, activity intensity and stored heart rate while retaining the raw activity category as context rather than guessing sleep stages from firmware-dependent category values.

### Xiaomi Smart Band 8 / 9 generation

Fitness recognizes Smart Band 7 Pro, Smart Band 8/8 Active/8 Pro and Smart Band 9/9 Active/9 Pro in the device catalog, but does not claim direct history synchronization for them yet. These devices belong to Xiaomi's newer protocol families rather than the legacy Huami FEE1 history transport. They remain catalogued so discovery and identity are correct while a separately verified transport is developed.

### Xiaomi Smart Band 10 / 10 Pro

Fitness recognizes Smart Band 10 and Smart Band 10 Pro and can use their standard Bluetooth Heart Rate Service when heart-rate sharing is enabled on the band. If Fitness discovers an accepted Band 10 without the standard heart-rate service active, it raises a fixable Home Assistant Repair with the exact on-band steps to enable Share HR; the Repair automatically clears as soon as the standard service appears. This is live heart-rate support, not a claim of proprietary history/workout synchronization.

### MyKronoz ZeTime

Fitness imports the documented activity, sleep and heart-rate history packets. Sleep BEGIN/END markers and explicit Deep/Light/Awake events are reconstructed into canonical `SleepRecord` nights. REM is left unset because the protocol does not expose it.

### HPlus protocol family

Fitness recognizes the unique HPlus BLE service and requests the documented read-only daily summaries. It imports steps, distance, calories, active minutes and daily minimum/maximum heart rate.

HPlus devices are known to store sleep data, but the public protocol documentation does not currently define the `DATA_SLEEP` payload precisely enough for an independent safe parser. HA-Fitness therefore does not guess at HPlus sleep records yet.

## Safety and performance model

Direct-history adapters follow the same low-impact contract:

- no private Bluetooth scanner;
- no permanent connection while idle;
- one bounded session per accepted/assigned device;
- one-hour normal synchronization cadence;
- sparse retry/backoff for busy, unavailable or failing devices;
- hard connection/session timeouts;
- bounded notification queues and record counts;
- no device-setting writes unless a protocol requires a non-destructive read request;
- one profile persistence transaction per fetched batch;
- raw intraday history is capped per metric and deduplicated, while compact daily canonical history remains capped by Fitness's existing per-metric history limit.

A physical wellness device can expose a manual **Sync device health history** action without being classified as a Smart workout archive. Workout-capable adapters such as Garmin/CYCPLUS remain separate.

## Why some Gadgetbridge-supported families are not implemented yet

Gadgetbridge is useful protocol research, but HA-Fitness does not embed or depend on Gadgetbridge. New adapters are independently implemented from documented wire-level facts and real-device captures.

Some families expose many health features in Gadgetbridge but do not yet have sufficiently complete public command/payload documentation for a conservative independent implementation. Authentication-heavy families also need a legitimate user-provided credential path before local support can be considered. Those devices are deliberately left unsupported rather than guessed.

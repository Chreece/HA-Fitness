# Local Garmin workout synchronization

HA-Fitness can read completed workouts directly from compatible Garmin wearables over Bluetooth. The Garmin phone app and Garmin cloud are not required for this path.

## What connects to what

The normal local path is:

```text
Garmin wearable -> Bluetooth -> Home Assistant -> HA-Fitness
```

Your phone does **not** connect to HA-Fitness for Garmin import. Garmin Connect may remain installed and paired with the wearable. HA-Fitness opens a short Bluetooth session only when it needs to synchronize, then disconnects so the normal Garmin ecosystem can continue using the wearable.

## Compatibility model

Garmin support is selected by Bluetooth/GATT capabilities, not by a watch-model list. HA-Fitness never checks for a specific Forerunner, Fenix, Instinct, Venu, vivoactive or other product name before choosing protocol behavior.

The adapter currently has these protocol-family backends:

- **GFDI V2 / Multi-Link** for Garmin devices exposing the modern Multi-Link characteristics and file service. This path supports the modern FileSync catalogue and compressed FIT transfer.
- **GFDI V1 / V0** for devices exposing the older direct GFDI characteristics. This path uses the classic Garmin directory/file-transfer protocol.

The architecture is therefore universal across those protocol families, but no implementation can promise that every Garmin product or firmware exposes one of them. Modern V2 Multi-Link has been validated end-to-end during HA-Fitness development. V0/V1 support uses the same capability-driven adapter and legacy Garmin file protocol, but real-device behavior can still vary by firmware.

### Smart discovery without a model whitelist

Automatic discovery requires Garmin **vendor/protocol evidence**, not a Bluetooth name. HA-Fitness can recognize a candidate from Garmin's Bluetooth company identifier, Garmin's assigned FE1F advertisement service, or a known GFDI V0/V1/V2 service UUID. A local name such as `Forerunner`, `Fenix`, `Venu`, `Garmin` or any future product name is display text only and is never sufficient to select support or a transport. This avoids probing arbitrary nearby devices merely because their name looks Garmin-like.

At startup, Fitness registers its narrow Bluetooth matchers with history replay disabled and then performs **one bounded replay** of the relevant entries already present in Home Assistant's Bluetooth cache. Opening **Smart workout devices** requests one short on-demand active scan and then replays the cache again. Concurrent guide scans are coalesced, repeated requests are rate-limited, cache traversal is bounded, and this discovery step never opens GATT. When a Bluetooth-backed Fitness device is deleted, Fitness clears only Home Assistant's matcher history for that address and requests one cached rediscovery after the short anti-resurrection quarantine; it does not start a private scan loop.

Advertisement evidence creates a **Garmin candidate**, not a supported-workout claim. Workout-history capability is granted only after the accepted device completes a bounded connected GATT/GFDI handshake. A device that definitively exposes none of the supported V2/V1/V0 transports is marked incompatible, removed from Garmin workout-device choices, and is not placed on a periodic retry timer. The user can explicitly remove/re-discover it later if firmware or capabilities change.

After the user accepts a Garmin candidate, the connected GATT surface is authoritative. V2 Multi-Link channel pairs are discovered from the actual `281x`/`282x` characteristic pairs exposed by the device rather than from a fixed channel table. Candidate transports are bounded and tried in capability order: V2 Multi-Link first, then V1, then V0. Each candidate handshake and the total negotiation have hard deadlines; a failed candidate is cleaned up before the next one is attempted.

Some Garmin V2 devices can request **reliable MLR mode** for a service. HA-Fitness does not guess at unverified MLR flow control. If that mode is required, the sync is rejected as unsupported, the connection is cleaned up, and retries are heavily backed off instead of leaving a Bluetooth task hanging.

## Setup in HA-Fitness

1. Make sure Home Assistant has a **connectable** Bluetooth route that can reach the Garmin wearable. A local Bluetooth adapter is the simplest route. A Bluetooth proxy may work only when the route supports the required connectable GATT operations; bonding/pairing support depends on the route.
2. Keep the Garmin wearable powered on and nearby. You do not normally need to disable Bluetooth on your phone.
3. Open **Smart workout devices** in the Fitness profile options. Opening the guide performs one short, bounded Bluetooth discovery sweep and lists strong Garmin candidates already visible to Home Assistant. A candidate may be shown as compatibility-check pending until the first bounded pairing/GATT verification; devices already proven incompatible are not shown in the Garmin procedure. Reopen the guide later to request another sweep; the provider enforces a cooldown.
4. Select the detected Garmin under **Smart workout devices** (or accept the same physical sensor from Local Sensors). Fitness does not ask you to retype its model or Bluetooth information. If another Fitness profile already owns stored-workout imports, you get an explicit keep/transfer choice; otherwise the current profile becomes the archive owner immediately.
5. Fitness immediately schedules the bounded archive worker. It automatically requests Bluetooth pairing if no Home Assistant bond exists. Keep Garmin Connect and the phone pairing in place. Approve any confirmation/code/passkey shown on the Garmin.
6. After pairing, capability discovery and unseen-workout import continue automatically in the same session and the device disconnects when finished. If everything works, there is nothing else to answer. If pairing needs help, Fitness raises one Repairs warning and the device setup screen tells you exactly what to do and offers a bounded **Retry now** action.

### First-time Bluetooth pairing

Pairing is automatic. When an accepted Garmin starts its first archive synchronization, HA-Fitness asks Home Assistant's normal proxy-aware Bluetooth connector to establish the connection with **pairing enabled**. If BlueZ/the selected Bluetooth route already has a bond, pairing is a no-op and synchronization continues immediately. If no bond exists, the Bluetooth stack starts the one-time pairing before Garmin service discovery.

The user should not need SSH, `bluetoothctl`, or a separate host-side setup procedure. Keep the Garmin nearby during the first sync. If the Garmin displays a confirmation, numeric comparison, passkey, or permission prompt, approve it **on the Garmin**. After the bond succeeds, the same bounded connection proceeds directly into capability discovery and workout import.

Pairing is still bounded by the Garmin session deadline: HA-Fitness makes one pairing-enabled connection attempt, never loops on interactive prompts, and cleans up on timeout/cancellation. If **Garmin last error** becomes `pairing_required`, Fitness also creates a Home Assistant Repairs warning. Open **Fitness > Smart workout devices**, select the Garmin, and follow the dedicated pairing-help screen. Keep the Garmin paired with the phone; put the Garmin into its Bluetooth/Phone pairing mode only so that it can accept Home Assistant as an additional host, approve any prompt on the Garmin, then choose **Retry now**. If Garmin warns that the existing phone pairing will be replaced or removed, cancel that device-side action and choose **Do this later**. The retry is still one bounded automatic pairing/sync attempt, not an interactive loop. On a Bluetooth route that cannot support bonding/pairing, HA-Fitness reports the failure and backs off instead of repeatedly waking the radio.

## Normal synchronization behavior

A successful automatic cycle is intentionally short lived:

```text
advertisement detected
  -> wait for the per-device sync interval
  -> acquire the device Bluetooth connection lock
  -> connect with a hard timeout
  -> discover a bounded set of GFDI candidates from GATT capabilities
  -> try V2 -> V1 -> V0 with per-candidate and total negotiation deadlines
  -> list a bounded activity catalogue
  -> download at most a small batch of unseen FIT activities
  -> validate/decode FIT data off the Home Assistant event loop
  -> checkpoint each completed file
  -> import through the canonical HA-Fitness workout merge
  -> disconnect
```

HA-Fitness does **not** keep Garmin GATT open while idle. After an up-to-date cycle it keeps only one tracked 30-minute timer per accepted/assigned Garmin. If the connectable route has disappeared, retries fall back to one sparse 30-minute presence check; a fresh verified Garmin advertisement can wake that sleeping presence check early without bypassing the normal sync interval or an error backoff. If a live workout owns the BLE device, archive retry waits five minutes rather than polling the live session continuously.

After a real GATT session closes, Fitness clears only Home Assistant's cached advertisement-history entry for that address. This follows Home Assistant's Bluetooth guidance for devices that need the next identical wake advertisement delivered after a GATT session; it does not start a scanner or connection by itself.

## Read-only policy

HA-Fitness treats the Garmin archive as a read-only source. Its local Garmin implementation does not expose commands to:

- mark Garmin files as synchronized;
- set Garmin file flags;
- archive workouts on the Garmin;
- delete workouts from the Garmin.

HA-Fitness keeps its own checkpoint of downloaded file identities and its own per-profile import state. This means Garmin Connect remains free to synchronize the same wearable according to Garmin's own rules.

## Reliability and Home Assistant safety

The local adapter is designed so a slow, busy, disconnected or malformed Garmin cannot monopolize Home Assistant:

- one connection lock is used per physical Bluetooth sensor;
- whole sync sessions and every major BLE/protocol stage have hard timeouts;
- notification, management and protocol queues are bounded;
- COBS/GFDI/protobuf messages, file lists, compressed downloads, inflated FIT files and decoded record counts all have explicit size/count ceilings; the GFDI receive ceiling matches its 16-bit wire length and the COBS buffer has only bounded framing headroom;
- only a small number of activities are downloaded per connection;
- compressed FIT inflation and FIT decoding run in an executor rather than on the HA event loop;
- every complete FIT is checkpointed before profile-history import;
- failed sessions use bounded exponential retry delays; after repeated ordinary failures the device enters a sparse two-hour degraded retry cadence instead of waking Bluetooth every 30 minutes forever;
- pairing-required states use a six-hour retry delay rather than retrying on every advertisement; definitively unsupported V2/V1/V0 transport is marked incompatible and receives no periodic retry timer;
- repeated Garmin advertisements use a rate-limited control path and cannot defeat the 30-minute sync interval, backlog cooldown or error backoff;
- stable advertisement payloads do not have to change for automatic sync: one tracked periodic timer provides the normal cadence, while Home Assistant advertisement history is cleared only after a completed GATT session so the next identical wake advertisement can be delivered;
- an unreachable Garmin falls back to a sparse 30-minute presence retry, and a live BLE owner is rechecked no faster than every five minutes;
- cancellation, unassignment, sensor removal and Home Assistant shutdown all use bounded cleanup;
- a Garmin sync will wait instead of stealing a BLE client currently owned by a live workout.

A manual **Sync workouts now** action schedules the same bounded background coordinator; pressing the button does not wait for a full Bluetooth transfer in the Home Assistant service/UI call.

## Historical workouts and deduplication

The modern FileSync request intentionally permits already-synchronized historical records because HA-Fitness does not use Garmin's synced flag as its own state. Returned file IDs are checkpointed locally. Only unseen files are downloaded, and already-decoded workout summaries can be imported into a newly assigned Fitness profile without requiring the wearable to resend the FIT file.

Garmin FileSync numeric `code` values are scoped to a response and can be reused for different types. HA-Fitness resolves the response-local code-to-name map and identifies activity FIT records by the resolved semantic type instead of hard-coding one numeric code.

The resulting FIT activity is normalized into the same `Workout` model used by other Fitness providers and then passes through the normal canonical merge, so a Garmin-local workout can enrich or merge with the same physical workout seen by another source.

## Strength workouts

When a Garmin activity contains FIT `set` messages, HA-Fitness preserves active/rest segment timing, reported repetitions, reported weight and known exercise categories as bounded structured workout data.

Garmin-reported values are retained rather than silently rewritten. A clearly implausible repetition rate can be flagged as a plausibility warning while the original value remains available. Unknown vendor fields are bounded and retained only as auxiliary metadata; HA-Fitness does not invent an exercise name from unknown fields.

If a Garmin session timestamp is not later than its start time but a valid elapsed duration exists, HA-Fitness derives the workout end from `start + elapsed` while retaining the original Garmin data in source metadata.

## Diagnostics

Accepted Garmin archive devices expose diagnostics such as:

- selected local backend (`auto`, V0/V1 or V2 Multi-Link);
- sync state;
- last attempt and last successful synchronization;
- device activity count, locally checkpointed count and pending count;
- retry count and last error;
- protocol version when reported by the device;
- latest imported Garmin workout;
- optional transferred-byte diagnostics.

Typical error states include:

- `connection_failed` — no usable connectable route, device busy/out of range, or connection failure;
- `pairing_required` — the Bluetooth host needs a one-time bond/authorization;
- `handshake_failed` — GFDI session did not become ready within its limit;
- `catalog_failed` — workout directory/FileSync catalogue could not be read safely;
- `transfer_interrupted` — an activity transfer did not complete within limits;
- `invalid_fit` — downloaded data failed bounded FIT validation;
- `unsupported_transport` — the device exposed a Garmin transport mode HA-Fitness intentionally does not implement safely (for example an MLR-only transfer path).

## Troubleshooting

If a Garmin is discovered but does not synchronize:

1. Confirm it is accepted under Local Sensors and assigned to at least one Fitness profile.
2. Check **Garmin last error** and **Garmin sync state**.
3. Bring the wearable close to a connectable Home Assistant Bluetooth route and press **Sync workouts now**.
4. If the error is `pairing_required`, put the Garmin in Bluetooth pairing mode if needed, keep it close, press **Sync workouts now**, and approve any confirmation/code on the Garmin. HA-Fitness performs the host-side pairing automatically.
5. If Garmin Connect is actively synchronizing at that exact moment, wait for it to finish and retry. Turning off phone Bluetooth should be a troubleshooting step, not a normal requirement.
6. If the state is `unsupported`, leave the device connected normally to Garmin Connect. HA-Fitness has deliberately stopped rather than attempting an unverified transport that could stall or corrupt the session.

For the broader Local Sensors architecture, see [LIVE_SENSORS.md](LIVE_SENSORS.md). For canonical completed-workout behavior, see [FEATURES.md](FEATURES.md) and [WORKOUT_CALENDAR.md](WORKOUT_CALENDAR.md).

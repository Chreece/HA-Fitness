# Smart workout devices

HA-Fitness treats a smart workout device as **one physical device with multiple capabilities and transports**. A watch can therefore expose live heart rate, battery, ANT+/Bluetooth routes and a local stored-workout archive without appearing as separate Fitness devices.

## Normal setup

1. Enable the Fitness Bluetooth adapter under **Sensors & Adapters**.
2. Open the Fitness profile that should own the device's stored workouts.
3. Open **Smart workout devices**.
4. Fitness requests one short, bounded Bluetooth discovery sweep and lists detected physical workout-archive devices. Devices can also appear automatically through normal Home Assistant Bluetooth discovery, just like other Fitness sensors.
5. Select the detected physical device. Fitness uses the detected model/name only as display metadata and does **not** ask you to type it again. If no other Fitness profile owns its stored-workout archive, selecting the device assigns it immediately to the current profile and starts the safe automatic setup.
6. Fitness performs host-side Bluetooth pairing, capability detection, workout download and disconnect automatically. Keep normal phone/vendor-app pairing in place. If the device itself shows a confirmation/code/passkey, approve it there.
7. Fitness asks a question only when there is a real decision or required action: an existing stored-workout owner must be kept/transferred, or automatic Bluetooth pairing needs the device put into pairing mode. These are presented as explicit choices rather than free-text fields.

## Automatic discovery and manual guides

The Smart workout devices page contains both detected physical devices and supported setup guides. For now the manual guided vendor flow includes Garmin. A guide may ask for a broad device type such as sport watch or bike computer when that changes the instructions, but it does not ask for a manually typed model name. The detected model is shown automatically after discovery. Actual support is always determined from verified manufacturer/protocol evidence and connected capabilities.

A blank or unfamiliar consumer model name does not make a device unsupported when its protocol capabilities are known. Vendor adapters may request pairing through the generic Bluetooth connection helper, but pairing remains bounded and never becomes an unbounded background interaction loop.

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

## Interaction policy

The setup flow follows a **no needless questions** rule:

- information Fitness can detect is displayed, not requested as text input;
- a healthy automatic connection continues without asking the user to confirm technical details;
- if the device requires a confirmation/passkey, the user is told exactly what to approve on the device;
- if automatic pairing fails because the device is not currently pairable, Fitness creates one Home Assistant Repairs warning and the Smart workout device screen offers **Retry now** or **Do this later**;
- repeated radio failures do not create repeated prompts or pairing loops. The existing bounded retry/backoff policy remains authoritative.

# Fitness Remote Gateway Protocol v1

Fitness remote gateways let a browser or future native sender collect fitness radio data near the athlete while Home Assistant can be on another network. The sender uses the authenticated Home Assistant WebSocket connection; radio decoding, sensor acceptance, profile assignment, workout capture, and history remain owned by HA-Fitness.

## Security model

- The sender must already be authenticated to Home Assistant.
- Every gateway call names the target Fitness `profile_entry_id`.
- Browser Bluetooth and USB pairing is initiated by the user and remains subject to browser permissions.
- Browser radio APIs require a secure context (normally HTTPS).
- No Bluetooth or ANT+ credentials are stored by Fitness. Browser permission handles are kept by the browser; Fitness stores only stable local device IDs needed to reconnect already-authorized devices.

A future restricted Fitness-only invite/session token can be layered above this protocol without changing the radio packet formats.

## Client hello

```json
{
  "type": "fitness/remote_gateway/hello",
  "profile_entry_id": "<fitness profile config entry>",
  "gateway_id": "<stable client UUID>",
  "client_name": "Chrome on laptop",
  "platform": "browser",
  "transports": ["bluetooth", "antplus"]
}
```

The response includes `protocol_version: 1`.

## Bluetooth transport

The gateway does not implement Fitness metric interpretation. It subscribes to standard Bluetooth SIG fitness measurement characteristics and forwards the raw characteristic value.

Register a device first:

```json
{
  "type": "fitness/remote_gateway/ble_device",
  "profile_entry_id": "<profile>",
  "gateway_id": "<gateway>",
  "device_id": "<sender stable device id>",
  "name": "Heart rate strap",
  "service_uuids": ["0000180d-0000-1000-8000-00805f9b34fb"],
  "characteristic_uuids": ["00002a37-0000-1000-8000-00805f9b34fb"]
}
```

Then batch notifications:

```json
{
  "type": "fitness/remote_gateway/ble_frames",
  "profile_entry_id": "<profile>",
  "gateway_id": "<gateway>",
  "device_id": "<device>",
  "frames": [
    {
      "characteristic_uuid": "00002a37-0000-1000-8000-00805f9b34fb",
      "payload": [0, 142]
    }
  ]
}
```

Supported v1 standard measurements are Heart Rate, Cycling Power, Cycling Speed and Cadence, Running Speed and Cadence, and FTMS Indoor Bike/Treadmill data. HA-Fitness reuses its normal Bluetooth decoders and automatically accepts/assigns the remote physical sensor to the selected Fitness profile.

## ANT+ transport

The sender owns ANT USB/native radio framing, but **does not decode ANT+ fitness profiles**. It forwards the channel identity and eight-byte ANT+ payload already extracted from the ANT serial frame:

```json
{
  "type": "fitness/remote_gateway/ant_packets",
  "profile_entry_id": "<profile>",
  "gateway_id": "<gateway>",
  "packets": [
    {
      "device_id": 12345,
      "device_type": 120,
      "transmission_type": 1,
      "payload": [0, 0, 0, 0, 0, 0, 0, 0],
      "adapter_id": "webusb:<gateway>"
    }
  ]
}
```

HA-Fitness feeds these packets into the existing remote ANT+ worker, profile decoders and sensor model. Once the semantic ANT+ device is confirmed, the remote sensor is accepted and assigned to the selected profile automatically.

Browser v1 uses Dynastream/Garmin ANTUSB2 (`0FCF:1008`) and ANTUSB-m (`0FCF:1009`) through WebUSB, enables extended receive messages, and scans the ANT+ network. Future Android/Windows/native radio senders should emit the same `ant_packets` schema.

> v1 identifies ANT+ radio devices by their ANT device number inside the existing HA-Fitness ANT receiver. Separate gateways with colliding ANT device numbers are therefore not intended to run simultaneously against one HA-Fitness instance yet. A future protocol revision can add gateway-scoped ANT identities without changing the sender's raw payload semantics.

## Gateway status

Send `fitness/remote_gateway/status` for ANT+ connection state so HA-Fitness diagnostics know whether the remote adapter is present.

## Local Google Cast

Local Cast is separate from radio transport. The browser uses Google's Web Sender SDK to discover/choose Cast devices on **the browser's current local network**. HA-Fitness authenticates the standard Home Assistant Cast receiver with the same system-user token model used by Home Assistant Cast (reusing the `Home Assistant Cast` system user when available, otherwise creating `Fitness TV Cast`). The per-session token is revoked when the sender ends the session and HA-Fitness restores its remaining TTL after Home Assistant restarts so abandoned Cast credentials are still cleaned up.

Commands:

- `fitness/tv/local_cast_credentials`
- `fitness/tv/local_cast_release`

The Cast receiver still needs an externally reachable HTTPS Home Assistant URL because the TV can be on another network.

## Future native senders

Android, iOS and Windows clients should implement this same protocol version and declare their radio transports in `hello`. A native client can use platform BLE/ANT+ APIs while HA-Fitness keeps all metric decoding and workout/profile behavior centralized.

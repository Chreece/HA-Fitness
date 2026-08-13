HA-Fitness Sensors & Adapters direct overlay

Extract this archive directly into ~/HA-Fitness.

Behavior:
- No ANT+/Bluetooth enable page in profile setup or profile Configure.
- A global "Sensors & Adapters" entry is created automatically for both new and existing Fitness profiles.
- ANT+ Adapter and Bluetooth Adapter devices always exist and start disabled on migration to this model.
- ANT+ / Bluetooth provider modules are loaded only when the adapter Enable switch is turned on.
- A translated "Sensors" collection device sits below the hub; merged physical sensors sit below Sensors.
- ANT+ remains preferred over Bluetooth for merged physical sensors.
- Existing profiles self-heal a missing Sensors & Adapters entry after Home Assistant reaches started state, so HA startup is not blocked.

Validation: 478 pytest tests passed in the build workspace.

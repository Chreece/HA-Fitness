# FAQ

## Why install Fitness if my watch integration already works?

Because they solve different problems. A Garmin, Polar, Oura, WHOOP, Strava or similar integration exposes that provider's data. Fitness consumes compatible Home Assistant entities and creates a provider-independent layer on top.

That matters when, for example, your chest strap supplied live heart rate, another sensor supplied power, and your watch uploaded the completed workout later. Fitness can reconcile those representations into one canonical workout while retaining locally calculated HR recovery, RPE and other Fitness-owned data.

## Does Fitness replace Garmin Connect, Strava, Polar, Hevy, etc.?

No. Install and configure the source integration first. Fitness reads its Home Assistant entities. Dedicated adapters understand known provider layouts; conservative fallback parsing can support other integrations when they expose a clear workout/sleep contract.

## Why are some entities missing?

Fitness is capability-aware. If a metric cannot be measured or calculated from the selected sources, Fitness does not fabricate it. Optional entities appear when meaningful data exists and can become unavailable when prerequisites temporarily disappear.

## Why does Fitness compare me with myself?

Many fitness signals depend on protocol, device, sport and individual physiology. Fitness therefore favors validated personal history and comparable workouts instead of turning every population reference into a universal good/bad threshold.

## What is RPE and why should I enter it?

RPE is your rating of perceived exertion: how hard the whole workout felt. Fitness uses whole-number session RPE from 1–10. Some providers can supply it; otherwise Fitness can ask you after the workout. You can always correct it later. Session-RPE load combines perceived effort with workout duration and complements sensor-derived load.

## Why can subjective RPE be useful when I already have heart rate?

Because perceived effort captures the internal experience of the whole session and can remain useful across exercise types where a single physiological signal is incomplete. The session-RPE method has been validated across multiple sports and is commonly recommended alongside objective measurements rather than as a replacement for them.

## What is Training Readiness?

Fitness Training Readiness is a transparent **Fitness-owned** 0–100 composite. It combines only available personal evidence from autonomic recovery, sleep, recent training recovery and post-exercise HR recovery. Missing domains are omitted and weights are renormalized; insufficient evidence produces no score. It is not a vendor score and is not a medical diagnosis.

## Does Fitness use AI to calculate my metrics?

No. Workout merging, unit conversion, history validation, formulas, RPE load, HR recovery and deterministic evaluations do not depend on AI. AI can optionally turn already-computed data into natural-language coaching or summaries.

## What can Home Assistant do with the data?

Anything normal HA entities can do: dashboards, notifications, TTS, automations, lighting, fans, media players and more. During a live workout, for example, Fitness can announce elapsed time and available live values or temporarily change compatible lights according to intensity.

## Is my data sent to Fitness servers?

Fitness itself is a Home Assistant custom integration and works from the entities available in your HA instance. External source integrations and any optional AI/TTS services have their own privacy behavior; check those projects/services separately.

## Is Fitness a medical device?

No. It is intended for fitness, training and wellness. Scientific references support individual methods, but Fitness composite scores and coaching are not clinical diagnoses and should not be used for medical decisions.

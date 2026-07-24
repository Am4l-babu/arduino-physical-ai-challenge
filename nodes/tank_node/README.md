# TANK node — fp2 (ESP32-C6)

Main valve, line flow, tank level, and pump current — one combined board for
the whole water side (docs/BOM_ORDER.md's "FLOW/POWER — tank node": one
ESP32-C6 for all of it). **This is a stated assumption, not a confirmed
physical layout** — see [nodes/README.md](../README.md). If the actual
wiring plan needs two separate boards (e.g. the main-line valve and the
roof tank turn out to be too far apart for one board's leads to reach),
`sim/virtual_house.py`'s valve+flow topics and `sim/virtual_pump.py`'s
tank+pump topics need to move back onto separate node-ids — the topic
contract below is what would need splitting.

**Status: compiles clean against the real ESP32-C6 toolchain (arduino-cli
1.5.0, esp32 core 3.3.9) in 5 configurations — full sensor suite, bare
board, and three partial mixes exercising the leak-reflex/valve interaction
from both directions. Never flashed or run on a physical board.** No valve,
CT clamp, level sensor, or flow meter hardware was in hand while this was
written; every calibration constant and pin assignment is first-draft.

## The hardwired reflex

The spec requires leak→valve response to work "with the hub dead, over
copper, not radio." This firmware's `loop()` checks the leak probes
**first, every iteration, before any MQTT or Wi-Fi code runs** — if either
probe reads wet for `LEAK_TRIP_READS` consecutive checks, it drives the
valve closed directly via GPIO, with no network round-trip. This is a
different (faster, more direct) mechanism than the hub's software water-
balance leak detection, which infers a leak from flow+occupancy over many
ticks — the probe reflex reacts to water physically touching a probe.

The reflex **latches**: once tripped, it takes `LEAK_CLEAR_READS`
consecutive dry reads to clear, and even then the valve is never
auto-reopened — that always requires a deliberate
`domora/cmd/main_valve/open` command, which this firmware refuses locally
while the latch is tripped (independent of whatever the hub's own
`hub/agents/safety.py` invariant decides — defense in depth, not a
duplicate of the same check).

**Dry-run pump protection is deliberately not a hardwired reflex.** It
requires correlating pump current against tank-level slope over time
(`hub/twin/virtual_sensors.py`'s `PumpProtection`) — exactly the kind of
multi-sensor reasoning the hub's software is for, not a single-sensor
instant reflex. Only leak→valve and gas→solenoid are hardwired per spec.

## The pump-cutoff relay gap

The ordered BOM has a CT clamp on the pump (sensing only — it measures
current, it can't switch anything) but **no relay/SSR to physically cut
pump power**. Confirmed with the project owner: a spare 5V single-channel
relay module is available and will be wired in. Most modules of this type
are **active-LOW** (driving the control pin LOW energizes the relay) —
`RELAY_ACTIVE_LOW` in `config.h` defaults to that; flip it if yours differs
(energized state should show a click + LED lit on most boards — verify on
the bench before wiring it in series with anything live).

## Topic contract

| Topic | Point | Source |
|---|---|---|
| `domora/fp2/tank.line/flow_lpm` | L/min | YF-S201 pulse count → the datasheet's fixed 7.5 Hz-per-L/min constant |
| `domora/fp2/water_tank/level_pct` | % | AJ-SR04M trigger/echo timing (HC-SR04-compatible mode) |
| `domora/fp2/main_valve/valve_state` | "open"/"closed" | **open-loop** — commanded state after a timed drive completes, no limit-switch feedback wired. This is fine: the hub's Verifier never trusts an actuator's own report anyway, it verifies against the independent flow sensor above |
| `domora/fp2/pump/current_a` | A | SCT-013-030 CT clamp, true-RMS over one ADC sampling window |
| `domora/fp2/pump/pump_state` | "on"/"off" | inferred from current > 0.2 A, not directly sensed |
| `domora/fp2/tank/status` | "online"/"offline" | birth message / LWT |

Subscribes: `domora/cmd/main_valve/+`, `domora/cmd/pump/+`. Safety
enforcement (what the *autonomous* planner may command) lives entirely in
`hub/agents/safety.py` — this firmware obeys whatever arrives on its
command topics, same as every other actuator in this architecture.

## What's a placeholder, not a measurement

- **CT clamp calibration** (`PUMP_CT_AMPS_PER_COUNT`): depends on the
  clamp's turns ratio *and* your burden resistor value — there's no safe
  universal constant. Calibrate against a known load once the hardware is
  in hand (the BOM's panel-node PZEM-004T is explicitly a "calibration
  reference" for exactly this kind of thing).
- **Level calibration** (`LEVEL_EMPTY_CM` / `LEVEL_FULL_CM`): placeholders.
  Measure the actual empty/full ultrasonic distances on the built tank.
- **Valve drive timing** (`VALVE_DRIVE_MAX_MS`, 15s default): no
  limit-switch feedback assumed. Time a real open/close cycle once the
  valve is in hand and tighten this — too long risks stalling the motor
  against its end-stop for longer than necessary.
- **Fail-safe boot states**: both valve relays de-energized at boot (no
  uncommanded motion until a real command arrives). The pump relay is also
  de-energized at boot, deliberately — *not* "leave the pump running": a
  watchdog reset that happens to land exactly when a dry-run cutoff was in
  effect must not silently re-energize the pump on reboot and undo the
  safety action. Resuming pump operation after any reset is always a
  deliberate `domora/cmd/pump/on`, never a boot default.

## Setup

Same pattern as `nodes/env_node/` — see that node's README for the general
flow (libraries, board package, `config.h`/`certs.h` from the `.example`
templates, `tools/gen_certs.py`). This node needs only `PubSubClient`
beyond the esp32 core (no Adafruit sensor libraries — flow/level/CT are all
read directly via interrupts/ADC/pulseIn, no vendor driver needed).

```
arduino-cli compile --fqbn esp32:esp32:esp32c6 nodes/tank_node
arduino-cli upload  --fqbn esp32:esp32:esp32c6 -p <COM port> nodes/tank_node
```

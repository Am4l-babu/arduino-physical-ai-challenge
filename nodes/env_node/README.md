# ENV node — env1/living (ESP32-C6)

Occupancy + comfort sensing for the §25.6 MVP, plus one actuator: an IR
blaster that drives an ordinary air conditioner — another brand's appliance,
on no network, with no API.

That actuator is the reason this node matters architecturally. Every other
actuator DOMORA commands can also be sensed: the valve reports its position,
the pump relay has a CT clamp on it. An IR appliance answers *nothing*. So
this node publishes only what it **transmitted** (`living_ac/ir_last_cmd`)
and never claims to know what the appliance did — that is decided at the
electrical panel by `hub/twin/virtual_sensors.py`'s `ACRunning`, from a
sensor the appliance cannot influence.

**Status: compiles clean (zero warnings, `--warnings all`) against the real
ESP32-C6 toolchain (arduino-cli 1.5.0, esp32 core 3.3.9) in six
configurations — full suite, bare board, blaster with and without radar,
capture-only, and sensors-without-IR. Never flashed or run on a physical
board, and the IR carrier and frame timings have never been checked against
a scope or a real appliance.** Treat pin numbers, sensor init, and above all
the IR timings as first-draft until bench-tested.

## Topic contract

Publishes exactly what `sim/virtual_house.py` already publishes for `env1` —
the hub cannot tell this board apart from the simulator:

| Topic | Point | Sensor |
|---|---|---|
| `domora/env1/living/radar` | 0/1 | LD2410C (still-human presence) |
| `domora/env1/living/pir` | 0/1 | HC-SR501 (motion) |
| `domora/env1/living/door` | 0/1 (1 = open) | reed contact |
| `domora/env1/living/temp_c` | °C | BME280 |
| `domora/env1/living/humidity_pct` | % | BME280 |
| `domora/env1/living/pressure_hpa` | hPa | BME280 |
| `domora/env1/living/lux` | lux | VEML7700 |
| `domora/env1/living/status` | "online"/"offline" | birth message / LWT |
| `domora/env1/living_ac/ir_last_cmd` | "on"/"off" | **what was transmitted, not appliance state** |

Subscribes to `domora/cmd/living_ac/+` (the only command topic this node
obeys). `sim/virtual_comfort.py` publishes and subscribes the identical set,
so the comfort loop verified in simulation accepts this board unchanged.

`hub/agents/observer.py` range-checks all of these (see `RANGES`); a reading
outside physical bounds is quarantined into `health.env1.<point>`, never
trusted into the twin silently. `ir_last_cmd` is registered there as an enum
with a note on why it is named for the transmission rather than the state.

## Learning your AC's codes

DOMORA does not decode brands. It replays the waveform your own remote
produces, which is why it works on an appliance no brand table covers.

1. Wire a TSOP38238 to `PIN_IR_RECV` and build with `HAS_IR_RECEIVER 1`.
2. Open the serial monitor at 115200, point your real remote at the TSOP and
   press the button you want DOMORA to learn.
3. The firmware prints a ready-to-paste `#define ..._TIMINGS { ... }` array.
   Paste it over `IR_AC_ON_TIMINGS` / `IR_AC_OFF_TIMINGS` in `config.h`.

**Capture the COOL button, not HEAT or a mode-cycle button.** The capability
table in `hub/agents/safety.py` admits `living_ac:on`/`off` and has no way to
check which mode a captured code selects — the button pressed here is the
only place that is enforced. This is stated in the invariant review in that
file, and it is a real gap, not a formality: a reversible heat pump learned
from its HEAT button would energize a heat-producing load while passing
every check in the hub.

The shipped `IR_AC_*_TIMINGS` values are a **placeholder** NEC-format frame.
They will not control your AC until replaced by a real capture.

### Hardware note

The IR LED and TSOP receiver are **not** in `docs/BOM_ORDER.md` — they are
pocket change, but they are parts you must add. Drive the LED through an NPN
(a GPIO cannot source useful IR current) with a series resistor; line of
sight to the indoor unit matters, and losing it is exactly the `ir_blind`
failure `sim/virtual_comfort.py` models.

## One firmware, role-driven

`config.h`'s `HAS_*` flags gate each sensor and the IR blaster — flip one to
`0` if that part hasn't arrived yet or isn't wired up; the rest of the node
still runs. Six configurations are compile-checked: full suite, bare board,
blaster-without-radar, blaster-with-radar, capture-only, and
sensors-without-IR. The blaster/radar pair is checked both ways on purpose,
because the empty-room guard inside `ir_send_command()` is itself behind
`#if HAS_LD2410`.

## Setup

1. **Libraries** (Arduino Library Manager or `arduino-cli lib install`):
   `PubSubClient`, `Adafruit BME280 Library`, `Adafruit VEML7700 Library`
   (pulls in `Adafruit Unified Sensor` + `Adafruit BusIO`).
2. **Board package:** esp32 core (Espressif), board `ESP32C6 Dev Module`
   (FQBN `esp32:esp32:esp32c6`).
3. **Local config** (gitignored — never commit Wi-Fi credentials or private
   keys):
   ```
   cp config.h.example config.h      # fill in Wi-Fi + MQTT + pins
   cp certs.h.example certs.h        # paste this node's PKI, see below
   ```
4. **mTLS identity**, from the repo root:
   ```
   python -m tools.gen_certs --out certs --nodes fp1 fp2 env1 perc1
   ```
   Paste `certs/ca.pem` → `CA_CERT`, `certs/env1.pem` → `CLIENT_CERT`,
   `certs/env1.key` → `CLIENT_KEY` in `certs.h`. The cert's CN (`env1`)
   doubles as the broker ACL username — it must match `NODE_ID` in `config.h`.
5. **LD2410C one-time config:** ships in UART report mode. Its digital OT1
   presence pin needs a one-time configuration pass (vendor config tool, or
   the Ai-Thinker LD2410 app over UART) before this firmware's plain
   `digitalRead()` will read anything meaningful. Not done in code — a bench
   setup step once the module is in hand.
6. **Compile / upload:**
   ```
   arduino-cli compile --fqbn esp32:esp32:esp32c6 nodes/env_node
   arduino-cli upload  --fqbn esp32:esp32:esp32c6 -p <COM port> nodes/env_node
   ```

## What's not done yet (bench-testing needed)

- Real sensor init hasn't been observed to succeed (`bme.begin()` / `veml.begin()`
  return values are trusted at compile-check time only).
- Pin assignments in `config.h.example` are placeholders — confirm against
  actual wiring before flashing.
- No debounce on the reed contact or PIR; add if bench testing shows chatter.
- Watchdog (`esp_task_wdt`, 20 s) is written against the exact installed
  esp32 core 3.3.9 header but has never actually tripped-and-recovered on a
  real board.
- **The IR path is entirely unverified in the physical sense.** The carrier
  frequency, duty cycle, mark/space accuracy and LED drive have never been
  measured; no appliance has ever responded to this firmware. Compiling is
  not evidence that a real AC will react. First bench test should be:
  capture a code, replay it, and confirm the unit beeps — *before* trusting
  the closed loop.
- `ir_send()` blocks for the length of a frame (tens of ms for a verbose AC
  remote), which stalls `mqtt.loop()` for that time. Fine at the 20 s
  watchdog, but unlike the tank node this board has no timing-critical
  reflex to starve — if one is ever added here, revisit this.
- The radar-based refusal to send `on` into an empty room (`ir_send_command`)
  reads the same LD2410 pin that needs the one-time UART configuration in
  step 5 above. Until that's done, `digitalRead` returns nothing meaningful
  and the guard will refuse every `on`. Configure the LD2410 before bench-
  testing the comfort loop, or build with `HAS_LD2410 0` to skip the guard.

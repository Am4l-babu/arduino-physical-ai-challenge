# ENV node — env1/living (ESP32-C6)

Occupancy + comfort sensing for the §25.6 MVP. Sensor-only: no actuators, no
commands to obey, so it never subscribes to `domora/cmd/#` and needs no
hardwired reflex (that's the FLOW/POWER node's job).

**Status: compiles clean against the real ESP32-C6 toolchain (arduino-cli
1.5.0, esp32 core 3.3.9) — full sensor suite, bare board, and every partial
mix in between. Never flashed or run on a physical board.** The parts were
ordered the same day this firmware was written; treat pin numbers, sensor
init, and timing as first-draft until bench-tested.

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

`hub/agents/observer.py` range-checks all of these (see `RANGES`); a reading
outside physical bounds is quarantined into `health.env1.<point>`, never
trusted into the twin silently.

## One firmware, role-driven

`config.h`'s `HAS_*` flags gate each sensor — flip one to `0` if that part
hasn't arrived yet or isn't wired up; the rest of the node still runs. All
three configurations (full suite, bare board, partial mix) have been
compile-checked.

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

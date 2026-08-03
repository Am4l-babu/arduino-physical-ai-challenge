# PANEL node — fp1 (ESP32-C6)

Whole-house electrical sensing: 3× SCT-013-030 CT clamps plus a PZEM-004T v3
reference meter (docs/BOM_ORDER.md's "FLOW/POWER — panel node"). This is the
node that feeds NILM — `main_panel.power_w` is the single twin point
`hub/agents/energy.py` reads to disaggregate the house, and this firmware is
the only real hardware source for it. `sim/virtual_loads.py` is its stand-in.

**Status: compiles clean against the real ESP32-C6 toolchain (arduino-cli
1.5.0, esp32 core 3.3.9) in 6 configurations — full suite, bare board,
CT-only, PZEM-only, mixed, and single-clamp — with zero warnings. Never
flashed or run on a physical board.** No CT clamp or PZEM was in hand while
this was written; every calibration constant and pin assignment is
first-draft.

## Sensing only — no actuation, by design

Unlike `nodes/tank_node/`, this firmware has no relay, no reflex, and
**subscribes to no command topic at all**. That is deliberate: spec §11.1
says panel work is "sensing-first, and any mains actuation goes through
certified contactors", and neither of the two closed loops in the §25.6 MVP
acts on mains. There is no code path by which this board can switch
anything.

⚠️ **The clamps go inside a live consumer unit.** Spec §11.1 requires an
electrician and an RCD. Clamp **one conductor only** — putting the clamp
around the whole cable makes the fields cancel and reads zero, which is the
classic first-day mistake (spec §14.4). Burden resistor at the node end,
twisted-pair leads.

## Where `power_w` comes from — the thing to understand here

A CT clamp measures **current and nothing else**. Real power needs voltage
and power factor too, so a clamp alone cannot report watts without assuming
both. There are two provenances, and `POWER_FROM_PZEM` in `config.h` picks
between them because they are not equally trustworthy:

| `POWER_FROM_PZEM` | `power_w` is | Assumptions |
|---|---|---|
| `1` (preferred) | the PZEM's `power()` reading, taken on the whole-house incomer | none — this is measured real power |
| `0` | `(aggregate CT current) × voltage × ASSUMED_POWER_FACTOR` | power factor always; voltage too, unless a PZEM is wired somewhere to measure it |

The derived path is not merely less precise — it is **wrong by a per-appliance
factor**, because each load is scaled by `assumed_PF / true_PF`. That is
measured, not asserted: `tests/test_nilm.py` runs the real NILM primitives
over `sim/virtual_loads.CtChain`, a model of this exact chain, and gets

| Appliance | true PF | true W | derived W | error |
|---|---|---|---|---|
| lamp (LED driver) | 0.95 | 60 | 59.6 | −0.7% |
| kettle (resistive) | 1.00 | 1800 | 1709.5 | −5.0% |
| fridge (compressor motor) | 0.62 | 150 | 229.9 | **+53.3%** |

NILM's **clustering survives** this — the three appliances still land in
three distinct, correctly-ordered clusters, which is the test that matters
for the demo. The **energy ledger does not**: a motor load's Wh is overstated
by half. Run `POWER_FROM_PZEM = 1` whenever the PZEM is on the incomer.

## Which clamps make up the whole house

`CTn_IN_AGGREGATE` decides what sums into the house current. Getting this
wrong silently doubles or halves the load and every NILM number inherits the
error without anything looking broken:

- A clamp on the incomer **already includes** every sub-circuit downstream of
  it. Marking both in-aggregate counts that circuit twice.
- A CT clamp is **unsigned** — it cannot tell import from export. A clamp on
  a solar feed must be `0`: its reading is generation, and there is no sign
  bit to correct the sum with.
- Three-phase supply is the case where all three are legitimately `1` — three
  separate incomers, no overlap, and they genuinely sum.

## Topic contract

| Topic | Point | Source |
|---|---|---|
| `domora/fp1/main_panel/power_w` | W | PZEM `power()`, or CT-derived — see above. **The one point NILM consumes** |
| `domora/fp1/main_panel/voltage_v` | V | PZEM, real measurement |
| `domora/fp1/main_panel/frequency_hz` | Hz | PZEM |
| `domora/fp1/main_panel/power_factor` | 0–1 | PZEM |
| `domora/fp1/main_panel/energy_kwh` | kWh | PZEM cumulative counter (library reports Wh; divided here). Wraps at 9999.99 |
| `domora/fp1/panel.ct1/current_a` | A | one clamp, true-RMS over a whole number of mains cycles |
| `domora/fp1/panel.ct2/current_a` | A | ditto |
| `domora/fp1/panel.ct3/current_a` | A | ditto |
| `domora/fp1/panel/status` | "online"/"offline" | birth message / LWT |

Subscribes: **nothing**.

Only `power_w` has a consumer today; the rest are recorded state. They cost
nothing extra to publish (the PZEM returns all six values from one Modbus
read) and spec §11.1 names voltage monitoring — brownout and surge logging —
as a reason this node exists. Studio's Sensor detail page is generic over any
twin point key, so they are browsable without further work. All of them are
range-checked in `hub/agents/observer.py` with tests in
`tests/test_observer.py`, including a test that a genuine surge or brownout
is **recorded rather than quarantined** — a range drawn tightly around 230 V
would silently discard the very events worth keeping.

Every PZEM getter returns `NAN` when the Modbus read fails. Each one is
guarded and simply omitted rather than published: silence is a signal in this
architecture (hub-side staleness detection handles it), a fabricated number
is not.

## What's a placeholder, not a measurement

- **CT calibration** (`CTn_AMPS_PER_COUNT`): depends on the clamp's turns
  ratio *and* your burden resistor value — there is no safe universal
  constant, which is exactly why the BOM buys the PZEM as a "calibration
  reference". Procedure: run a known steady resistive load (a kettle is
  ideal — PF ≈ 1, so the PZEM's watts ÷ its volts gives true amps), read the
  PZEM, and scale until the clamp agrees. Per-channel, because burden
  resistors have real tolerance and three clamps will not calibrate alike.
- **Noise floor** (`CT_NOISE_FLOOR_A`, 0.05 A): measure what the clamps
  report with the breaker off and set it just above that. Too low and the
  house grows a phantom always-on baseline plus a stream of fake NILM edges;
  too high and small real loads vanish.
- **Sampling window** (`CT_SAMPLE_WINDOW_MS`, 100 ms): exactly 5 cycles at
  50 Hz. Sampling a whole number of mains cycles is what stops the RMS
  wobbling with where in the waveform the window happened to open. Use a
  multiple of 16.67 ms for 60 Hz.
- **Pins**: the three CT pins must be ADC-capable on your specific C6 devkit;
  check the board's pinout before wiring.
- **`ASSUMED_POWER_FACTOR` / `NOMINAL_VOLTAGE_V`**: only used on the derived
  path, and both are guesses by definition. See the error table above.

The DC midpoint for the RMS calculation is **measured, not assumed** to be
half of full scale — the bias network that lifts the clamp's AC output into
the ADC range is two real resistors and never lands exactly on VCC/2, and any
residual offset inflates every reading, since RMS cannot tell an offset from
signal. One pass computes both: `variance = mean(x²) − mean(x)²`.

## Setup

Same pattern as `nodes/env_node/` — see that node's README for the general
flow (board package, `config.h`/`certs.h` from the `.example` templates,
`tools/gen_certs.py`).

Libraries beyond the esp32 core:

```
arduino-cli lib install PubSubClient
arduino-cli lib install PZEM004Tv30      # Jakub Mandula, v1.2.1 — only if HAS_PZEM
```

`PZEM004Tv30` is the canonical driver for the BOM's exact part. It is used
rather than hand-rolled Modbus-RTU deliberately: a hand-written CRC16 and
frame parser cannot be bench-tested without the hardware in hand, and getting
a binary protocol subtly wrong is a bug that only shows up as silent `NAN`s on
demo day.

```
arduino-cli compile --fqbn esp32:esp32:esp32c6 nodes/panel_node
arduino-cli upload  --fqbn esp32:esp32:esp32c6 -p <COM port> nodes/panel_node
```

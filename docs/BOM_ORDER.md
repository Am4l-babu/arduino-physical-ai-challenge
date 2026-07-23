# BOM — Order List (competition demo scope, §25.6)

Scope: **not** the full Tier M house (§6.1, ≈₹22k) — this is the ≈₹15k MVP
subset from spec §25.6: UNO Q hub + exactly 4 physical nodes (ENV-living,
FLOW/POWER-panel, FLOW/POWER-tank, PERCEPTION-kitchen). Anything not needed
for the two verified closed loops (leak→valve→verify; pump dry-run→cut→verify)
or the occupancy/comfort read-out is deliberately left off this list — it
lives in Tier R/P (§6.2–6.3) for later.

Prices are the spec's July-2026 street estimates (±30%, hobby market).
**Verify current price/stock before ordering — this file is a checklist,
not a live quote.**

## Order now — long lead time risk

| Item | Qty | Est. ₹ | Source channel | Note |
|---|---|---|---|---|
| Arduino UNO Q (hub) | 1 | 5,000 | Arduino Store / authorized IN distributor (check Robu.in, official Arduino resellers) | **Order first.** Competition-mandated board; import/distributor stock is the one item PLAN.md flags as the real week-1 risk. |

## Node build — order together (domestic hobby vendors: Robu.in, Robocraze, ElectronicsComp, SunRom, Quartz Components, Amazon.in)

### FLOW/POWER — panel node
| Item | Qty | Unit ₹ | Total ₹ |
|---|---|---|---|
| ESP32-C6 DevKit | 1 | 550 | 550 |
| SCT-013-030 CT clamp | 3 | 300 | 900 |
| PZEM-004T v3 (calibration reference) | 1 | 700 | 700 |
| **Subtotal** | | | **2,150** |

### FLOW/POWER — tank node
| Item | Qty | Unit ₹ | Total ₹ |
|---|---|---|---|
| ESP32-C6 DevKit | 1 | 550 | 550 |
| AJ-SR04M waterproof ultrasonic (level) | 1 | 350 | 350 |
| SCT-013-030 CT clamp (pump) | 1 | 300 | 300 |
| YF-S201 flow sensor | 1 | 250 | 250 |
| Motorized ball valve ½″ 12 V (CWX-15 or equiv.) | 1 | 1,400 | 1,400 |
| Water leak probe pairs | 2 | 80 | 160 |
| 12 V/2 A PSU (valve) | 1 | 250 | 250 |
| 5 V/3 A PSU (node) | 1 | 250 | 250 |
| **Subtotal** | | | **3,510** |

### ENV — living room node
| Item | Qty | Unit ₹ | Total ₹ |
|---|---|---|---|
| ESP32-C6 DevKit | 1 | 550 | 550 |
| LD2410C mmWave radar | 1 | 400 | 400 |
| PIR HC-SR501 | 1 | 90 | 90 |
| BME280 module | 1 | 300 | 300 |
| VEML7700 lux | 1 | 250 | 250 |
| Reed contact (door) | 1 | 60 | 60 |
| 5 V/3 A PSU | 1 | 250 | 250 |
| **Subtotal** | | | **1,900** |

### PERCEPTION — kitchen node
| Item | Qty | Unit ₹ | Total ₹ |
|---|---|---|---|
| ESP32-S3 DevKit N8R8 | 1 | 850 | 850 |
| INMP441 I2S mic | 1 | 280 | 280 |
| 5 V/3 A PSU | 1 | 250 | 250 |
| **Subtotal** | | | **1,380** |

### Shared build-out
| Item | Qty | Est. ₹ | Note |
|---|---|---|---|
| Buzzers, LEDs, level shifters, wire, connectors, headers, breadboard/protoboard | — | 800 | Scaled down from Tier M's whole-house ₹1,500 |
| Enclosures (ABS IP54 for tank/wet areas) + DIN mounting bits | — | 500 | Tank node is the only wet-area box for the demo rig |
| 5 V/3 A PSU (hub) | 1 | 250 | |
| **Subtotal** | | **1,550** | |

## Running total

| Section | ₹ |
|---|---|
| Hub | 5,000 |
| FLOW/POWER panel | 2,150 |
| FLOW/POWER tank | 3,510 |
| ENV living | 1,900 |
| PERCEPTION kitchen | 1,380 |
| Shared build-out | 1,550 |
| **Total** | **≈ 15,490** |

Matches spec §25.6 ("≈₹15k hardware"). Do not add Tier R/P items
(SCD40, extra valves, UPS, thermal cam, etc.) to this order — they're
explicitly out of MVP scope; see §6.2–6.4 if a future phase needs them.

## Ordering notes

- **UNO Q first, separately** — it's the one part with real import/stock
  lead time; everything else is commodity hobby stock available same-week
  from domestic vendors.
- Buy 1 spare of anything solder-destructive to prototype with (reed
  contacts, leak probes) — cheap insurance, not scope creep.
- MQ-6/MQ-7 gas sensors are **not** in this list: §25.6's MVP has no gas
  loop (kitchen node here is PERCEPTION/audio only). If the gas-leaf-reflex
  demo gets pulled forward too, add MQ-6 + LPG solenoid from Tier R (§6.2)
  as a separate follow-up order — don't fold it into this one silently.
- Verify street prices before checkout; spec explicitly flags ±30% hobby-market
  swing since July 2026.

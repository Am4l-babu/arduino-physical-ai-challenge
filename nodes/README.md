# Nodes — leaf firmware

One firmware, two targets (ESP32-C6, ESP32-S3), role-driven by config —
five MCU families was rejected in the spec (§7.2) as a maintenance tax.

| Node type | MQTT identity | Target | Role |
|---|---|---|---|
| ENV | `env1` | ESP32-C6 | BME280, LD2410 radar, PIR, reed, leak ADC, buzzer |
| FLOW/POWER — panel | `fp1` | ESP32-C6 | 3x CT clamp + PZEM (whole-house NILM) |
| TANK (valve + flow + level + pump) | `fp2` | ESP32-C6 | Main valve driver, line flow meter, tank level probe, pump CT, leak probes + **hardwired reflex** |
| PERCEPTION | `perc1` | ESP32-S3 | INMP441 mic → on-node TinyML → events only, never audio |

**One identity, one physical board, one mTLS cert** (`tools/gen_certs.py`'s CN
doubles as the broker ACL username — a board can't hold two identities).
`docs/BOM_ORDER.md`'s "FLOW/POWER — tank node" line item budgets exactly
**one** ESP32-C6 for valve + line flow + tank level + pump CT + leak probes
combined — so that's modeled as one node (`fp2`), not two, in `sim/` and the
PKI defaults. **This is an assumption, not a confirmed physical layout** —
the actual wiring/cabling plan (can one board's leads reach both the main-line
valve and the roof tank in the demo rig?) hasn't been decided yet. If it turns
out two boards are needed, `sim/virtual_house.py`'s valve+flow topics and
`sim/virtual_pump.py`'s tank+pump topics need to move back onto separate
node-ids — a small, mechanical change now that the assumption is written down
in one place instead of scattered implicitly across files.

Firmware rules (mirror the hub's agent contracts):

1. **Reflexes are local.** Leak→valve and gas→solenoid work with the hub
   dead, over copper, not radio. The hub adds context, never the trigger.
2. **Publish features, not waveforms.** CT waveforms and mel-spectrograms
   stay on-node; the wire carries `{value|event, confidence, t}`.
3. **Birth/death messages.** Every node announces on boot and sets an MQTT
   LWT so hub-side staleness detection is immediate.
4. **Safe reboot states.** All outputs to fail-safe on watchdog reset
   (spec §16.2: fail-safe is chosen per asset, not a slogan).

`env_node/env_node.ino` is written and compile-checked against the real
ESP32-C6 toolchain (arduino-cli, esp32 core 3.3.9) — see
[env_node/README.md](env_node/README.md) for setup — but not yet flashed to
hardware. Role/room/sensor-mix currently come from a local `config.h`
(gitignored — copy `config.h.example`), not yet a flashed SPIFFS/NVS
`node.yaml`; that layer is deferred until the config pattern proves out on
one real board.

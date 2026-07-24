# Nodes — leaf firmware

One firmware, two targets (ESP32-C6, ESP32-S3), role-driven by config —
five MCU families was rejected in the spec (§7.2) as a maintenance tax.

| Node type | Target | Role |
|---|---|---|
| ENV | ESP32-C6 | BME280, LD2410 radar, PIR, reeds, leak ADC, buzzer |
| FLOW/POWER | ESP32-C6 | CT clamps / PZEM, flow, valve driver, SSR + **hardwired reflexes** |
| PERCEPTION | ESP32-S3 | INMP441 mic → on-node TinyML → events only, never audio |

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

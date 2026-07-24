# PLAN — Competition Prototype (8 weeks, solo)

Scope contract: the MVP in [docs/DOMORA_SPEC.md](docs/DOMORA_SPEC.md) §25.6 —
UNO Q hub + 4 nodes, two verified closed loops, Three.js dashboard, demo rig.
**New ideas do not enter this plan; they go to the spec's Phase 2 list.**

| Week | Deliverable | Exit test |
|---|---|---|
| 1 | ✅ Agent runtime + simulator + tests (this repo, done) · ✅ **UNO Q benchmark**: hub runtime + SQLite under 10 fake nodes' load, run on the real board — 30.3x headroom, comfortable | ✅ Loop demo runs on the UNO Q itself with headroom (30.3x, no LAN-sidecar fallback needed) |
| 2 | ✅ MQTT bridge (`hub/services/`): real Mosquitto + mTLS, `sim` publishes through it · SQLite journaling of twin + actions — **verified beyond the dev PC**: Mosquitto deployed on the UNO Q itself, reached over real Wi-Fi from a separate machine | ✅ Same tests pass with the real broker in the middle (proven on the real board, real network, not just localhost) |
| 3 | ENV node firmware (ESP32-C6): BME280 + radar + PIR + reed → MQTT · node config from `node.yaml` | Real room feeds the twin; occupancy fusion works on live data |
| 4 | FLOW/POWER node: CT clamp + PZEM + YF-S201 + motorized valve · **hardwired leak reflex** independent of hub | Bench loop: real water, real valve, verified closure |
| 5 | Dashboard v1: Three.js schematic house + WebSocket live points + event timeline with cause→evidence→action→verify chains | Judge-readable on a phone served from the hub |
| 6 | NILM event-clustering on panel CT + interactive labelling · tank node (level + pump current) with dry-run cutoff loop | Kettle/lamp identified live; dry-run cut verified |
| 7 | Demo rig build (2-room model, clear tubing, resettable) · perception node stretch: 6 audio events on S3 | Full 6-minute demo sequence runs 3× consecutively untouched |
| 8 | Freeze. Video, poster, pitch Q&A drill, spare parts, travel router | Reset-to-demo ≤ 60 s; failure-path demo rehearsed |

Risks and fallbacks: spec §25.8. The schedule killer is integration, not
features — anything slipping past week 6 gets cut, not compressed.

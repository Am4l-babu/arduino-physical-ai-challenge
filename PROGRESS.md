# DOMORA — Progress

> Status board. Solo project — no assignee column. Update when starting or
> finishing a component; the Activity Log is append-only.

## Legend

📋 Todo · 🔄 Ongoing · ✅ Done · 🚫 Blocked

## Software (hub runtime)

| Component | Status | Notes |
| --- | --- | --- |
| Engineering spec + critical review | ✅ Done | docs/DOMORA_SPEC.md — 25 sections, MVP defined in §25.6 |
| Event bus + twin state + knowledge graph | ✅ Done | hub/core, hub/twin — stdlib only |
| Agent loop (observe→…→verify) | ✅ Done | 7 agents, expectation contract, capability-table safety |
| Virtual house simulator + fault injection | ✅ Done | sim/ — leak + stuck-valve scenarios |
| Closed-loop tests | ✅ Done | 3 passing (`python -m pytest tests/ -q`) |
| Benchmark harness (tools/benchmark.py) | ✅ Done | Full pipeline + SQLite under synthetic node load; verdict thresholds baked in. Dev-PC dry run: 24.5k msg/s = 245× headroom over a 10-node house |
| UNO Q benchmark run (week-1 gate) | 🚫 Blocked | Needs the board in hand — `python -m tools.benchmark` on the UNO Q decides the LAN-sidecar question |
| MQTT bridge (real broker) | ✅ Done | hub/services/mqtt_bridge.py — role-filtered hub/node directions (loop-proof), queue-pumped into the single-threaded twin. E2E test spawns a private Mosquitto: leak loop closes across the wire |
| MQTT mTLS + per-node certs | ✅ Done | tools/gen_certs.py provisions the house PKI (CA + broker + per-identity client certs); cert CN = broker username, ACL confines each node to its own namespace. 3 tests: TLS roundtrip works, cert-less client rejected, foreign-namespace publish dropped |
| SQLite journaling (twin + action log) | ✅ Done | hub/services/store.py — WAL mode, journals every twin change + full action audit trail (cause/evidence/expectation/outcome); 2 tests; `--journal db` flag on hub.main |
| NILM event-clustering | ✅ Done | hub/twin/nilm.py + EnergySense agent: edge detection between stable levels, incremental signature clustering, on/off pairing → per-appliance energy ledger, interactive labelling (label_nearest). `--scenario energy` recovers fridge/kettle/lamp from the aggregate alone (kettle 7.49 Wh vs 7.5 true). 4 tests |
| Dashboard (Three.js + WS) | 📋 Todo | Week 5 |

## Hardware

| Component | Status | Notes |
| --- | --- | --- |
| BOM ordering (Tier M subset, ≈₹15k) | 🔄 Ongoing | docs/BOM_ORDER.md — itemized order list per node (§25.6 MVP scope, not full Tier M), ≈₹15,490 total. UNO Q flagged as order-first (import lead time); rest is domestic hobby stock. Awaiting actual purchase |
| ENV node firmware (ESP32-C6) | 📋 Todo | One firmware, role-driven config |
| FLOW/POWER node + valve + leak reflex | 📋 Todo | Hardwired reflex independent of hub |
| Tank node (level + pump CT) | 📋 Todo | Dry-run cutoff loop |
| Perception node (S3 audio) | 📋 Todo | Stretch — closed set of 6 events |
| Demo rig (2-room model, water loop) | 📋 Todo | Resettable ≤ 60 s |

## Activity Log

| Date | Action |
| --- | --- |
| 2026-07-18 | Spec written (docs/DOMORA_SPEC.md) |
| 2026-07-18 | Repo scaffolded: agent runtime, twin, simulator, tests — both closed-loop scenarios verified green |
| 2026-07-18 | SQLite journaling shipped (store.py + twin hook + tests) — action audit trail captures cause→evidence→expectation→outcome |
| 2026-07-18 | Benchmark harness shipped; dev-PC dry run 245× headroom. WAL sidecar sizing bug found and fixed. Real gate awaits UNO Q hardware — 5 tests green |
| 2026-07-18 | Installed Mosquitto 2.1.2 + paho-mqtt 2.1.0; MQTT bridge shipped and proven end-to-end over a real broker (field node and hub sharing nothing but MQTT) — 6 tests green |
| 2026-07-18 | mTLS shipped: PKI provisioning tool + TLS in the bridge + locked broker config. Proven: certified roundtrip, cert-less rejection, ACL namespace confinement — 9 tests green. Week 2 of PLAN.md complete |
| 2026-07-19 | NILM shipped (week-6 item pulled forward): disaggregates fridge/kettle/lamp from one noisy aggregate power stream, energy ledger within 1% of truth, labelling flow demoed in `--scenario energy` — 13 tests green |
| 2026-07-23 | BOM order list drafted (docs/BOM_ORDER.md): itemized per-node breakdown for the §25.6 MVP subset (not full Tier M), ≈₹15,490 total, UNO Q called out as the order-first/lead-time item |

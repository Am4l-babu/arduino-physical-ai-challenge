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
| Closed-loop tests | ✅ Done | leak + stuck-valve scenarios (`python -m pytest tests/ -q`) |
| Pump dry-run protection loop (2nd MVP loop) | ✅ Done | sim/virtual_pump.py (tank+pump, dry-run + welded-relay fault injection) · PumpProtection virtual sensor (pump running current + flat tank level → dry-run suspected) · planner `_rule_dryrun_response` cuts pump, verified via CT clamp independent of relay ACK. `--scenario dryrun` / `dryrun_stuck`. No capability-table change (`pump:off` already listed; `pump:on` already unrepresentable = the spec's FAULT-state guard for free). 3 tests: cut verified, welded relay escalates + marks pump suspect, healthy pump never trips. **Second of the two §25.6 closed loops now closed** |
| Benchmark harness (tools/benchmark.py) | ✅ Done | Full pipeline + SQLite under synthetic node load; verdict thresholds baked in. Dev-PC dry run: 24.5k msg/s = 245× headroom over a 10-node house |
| UNO Q benchmark run (week-1 gate) | 🚫 Blocked | Needs the board in hand — `python -m tools.benchmark` on the UNO Q decides the LAN-sidecar question |
| MQTT bridge (real broker) | ✅ Done | hub/services/mqtt_bridge.py — role-filtered hub/node directions (loop-proof), queue-pumped into the single-threaded twin. E2E test spawns a private Mosquitto: leak loop closes across the wire |
| MQTT mTLS + per-node certs | ✅ Done | tools/gen_certs.py provisions the house PKI (CA + broker + per-identity client certs); cert CN = broker username, ACL confines each node to its own namespace. 3 tests: TLS roundtrip works, cert-less client rejected, foreign-namespace publish dropped |
| SQLite journaling (twin + action log) | ✅ Done | hub/services/store.py — WAL mode, journals every twin change + full action audit trail (cause/evidence/expectation/outcome); 2 tests; `--journal db` flag on hub.main |
| NILM event-clustering | ✅ Done | hub/twin/nilm.py + EnergySense agent: edge detection between stable levels, incremental signature clustering, on/off pairing → per-appliance energy ledger, interactive labelling (label_nearest). `--scenario energy` recovers fridge/kettle/lamp from the aggregate alone (kettle 7.49 Wh vs 7.5 true). 4 tests |
| Dashboard — live WS transport + operations view | ✅ Done | hub/services/api.py — stdlib-only HTTP + RFC 6455 WebSocket (no FastAPI, runs dependency-free on the UNO Q). Taps the live bus + twin, broadcasts every event/point, replays history to late joiners, per-client queue so a slow phone can't stall the hub. dashboard/index.html renders the cause→evidence→command→verify timeline + live points table, theme-aware. 2 tests: a real WS client watches the leak loop close and the stuck valve escalate. `python -m hub.services.api --scenario stuck` |
| Dashboard — journal playback (scrub-back) | ✅ Done | hub/services/store.py `JournalReader` rebuilds a recorded run as the same frame contract the live WS uses; `/playback.json` serves it; dashboard scrubber replays through the identical renderers. `python -m hub.main --scenario stuck --journal demo.db` then `python -m hub.services.api --playback demo.db`. 2 tests: timeline reconstruction + endpoint |
| Dashboard — twin view (schematic SVG) | ✅ Done | dashboard/index.html — inline-SVG floor plan bound to live twin points: occupancy glow (house.occupied), tank level bar (water_tank.level_pct), animated pipe flow (tank.line.flow_lpm) that turns red on virtual.water.leak_suspected, main-valve state + pulsing suspect badge (health.main_valve), status strip. Twin/Operations tab toggle. **Deviation from spec §10 (Three.js):** built dependency-free SVG instead — no library to vendor, no CDN at the venue, honors "data *is* the graphics". 3D remains a Phase-2 polish option. Verified headless (node DOM shim) against recorded leak (valve closed, nominal) and stuck (valve suspect, flood ongoing) runs, incl. mid-incident scrub at t=35 |

## Hardware

| Component | Status | Notes |
| --- | --- | --- |
| BOM ordering (Tier M subset, ≈₹15k) | ✅ Done | docs/BOM_ORDER.md — ordered 2026-07-23 (§25.6 MVP scope, ≈₹15,490). Awaiting delivery; UNO Q is the lead-time item. Firmware (weeks 3–4) and demo rig unblock as parts arrive |
| ENV node firmware (ESP32-C6) | 📋 Todo | One firmware, role-driven config |
| FLOW/POWER node + valve + leak reflex | 📋 Todo | Hardwired reflex independent of hub |
| Tank node (level + pump CT) | 📋 Todo | Hardware pending. Dry-run cutoff loop logic already proven in sim + tests (see software table); firmware wires the real level probe + pump CT + relay to the same topic contract |
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
| 2026-07-23 | Components ordered (§25.6 MVP subset, ≈₹15,490) — awaiting delivery; firmware/rig work unblocks on arrival |
| 2026-07-23 | Dashboard slice 1 shipped (week-5 item pulled forward while parts ship): stdlib-only HTTP+WebSocket server (hub/services/api.py, no FastAPI) taps the live bus+twin; dashboard/index.html renders the cause→evidence→command→verify timeline + live points, theme-aware; per-client queue keeps a slow browser from stalling the hub. Verified live: page serves, 725 events + 1259 points streamed, stuck-valve escalation reached the client. 15 tests green. Three.js house + journal playback remain |
| 2026-07-23 | Dashboard slice 2 shipped: journal playback. store.JournalReader rebuilds a recorded run as the live frame contract; /playback.json serves it; the dashboard grows a scrubber (play/pause + range) that replays the incident through the same renderers. Verified live: stuck run → 1261-frame timeline (t 0–119), dispatched shutoff + escalation reconstructed. 17 tests green. Three.js twin view is the last week-5 item |
| 2026-07-23 | Dashboard slice 3 shipped: schematic SVG twin view (Twin/Operations tabs) bound to live twin points — occupancy glow, tank level, animated leak-aware pipe flow, valve state + suspect badge. Chose dependency-free SVG over spec §10's Three.js (nothing to vendor, no venue CDN). Verified by running the real dashboard JS headless (node DOM shim) against recorded leak/stuck runs + a mid-incident scrub — visual states correct on both paths. **Week 5 (dashboard) complete.** 17 tests green |
| 2026-07-23 | Second closed loop shipped: pump dry-run protection (week-6 item). sim/virtual_pump.py + PumpProtection virtual sensor + planner dry-run rule; cut verified through the CT clamp independent of the relay ACK. Both paths proven (`dryrun` verified at t=33; `dryrun_stuck` retries, escalates, marks pump suspect at t=50) and streamed live over the dashboard. No safety capability-table change needed. **Both §25.6 closed loops now closed.** 20 tests green |

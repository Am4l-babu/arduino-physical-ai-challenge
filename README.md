# DOMORA — Digital Operating Model for Residential Awareness

> A Physical AI operating system for the home: a live digital twin that
> **observes, thinks, plans with expected effects, acts, and verifies its own
> actions against independent physical evidence.** A house that checks its work.

Built for the **Arduino Physical AI Challenge**. Full engineering spec + critical
design review: [docs/DOMORA_SPEC.md](docs/DOMORA_SPEC.md).

## Try the closed loop right now (no hardware, no dependencies)

```bash
python -m hub.main --scenario leak    # hidden leak -> detected -> valve closed -> VERIFIED
python -m hub.main --scenario stuck   # valve jammed -> verification fails -> retry -> ESCALATE
python -m pytest tests/ -q            # 3 regression tests over both loops + safety table
```

The same agent code that will run on the Arduino UNO Q runs here against a
simulated house. Sample output of the flagship failure path:

```text
[t=034] understander | impossible state: flow=1.96 L/min with 0 fixtures open and house empty -> leak suspected
[t=034] planner      | plan: close main_valve (upstream of leak) — expect line flow < 0.1 L/min within 10 ticks
[t=034] actor        | dispatch action#1: domora/cmd/main_valve/close
[t=045] verifier     | expectation NOT met (flow=2.08) — retrying once
[t=056] verifier     | VERIFICATION FAILED — main_valve marked suspect, ESCALATING to human
```

No competing smart-home system shows you a failure being *caught*. That is the product.

## Repository map

```text
├── README.md              you are here
├── ARCHITECTURE.md        tiers, planes, topic contract, diagrams
├── PLAN.md                8-week build plan to the competition prototype
├── PROGRESS.md            status board (solo project — no assignee column)
├── CLAUDE.md              working rules for AI-assisted sessions in this repo
├── docs/
│   ├── DOMORA_SPEC.md     the full 25-section spec + critical review
│   └── AGENTS.md          the cognitive loop: how each agent thinks/acts/verifies
├── hub/                   edge runtime (Python, runs on UNO Q Linux side)
│   ├── core/bus.py        MQTT-style in-process event bus
│   ├── twin/              state store · knowledge graph · virtual sensors
│   ├── agents/            observer · understander · predictor · planner
│   │                      · safety · actor · verifier
│   ├── config/house.json  the knowledge graph seed (assets + typed edges)
│   └── main.py            orchestrator + scenario runner
├── sim/virtual_house.py   simulated physics + configurable faults
├── nodes/                 ESP32 firmware (one template, role-driven)
├── dashboard/             Three.js twin view (Phase 1, week 5)
└── tests/                 closed-loop regression tests
```

## Principles

1. **Verification is the product.** Every actuation states its expected effect
   before dispatch and is confirmed by an independent sensor or escalated.
2. **Safety is dumb on purpose.** Capability tables and invariants, no ML,
   auditable at 2 a.m. Life-safety stays with certified devices.
3. **Local-first, provably.** The loop runs with the WAN cable pulled.
4. **Simulation-first.** Every behavior lands in `sim/` + `tests/` before it
   touches hardware — the replay harness is the CI gate for new automation rules.

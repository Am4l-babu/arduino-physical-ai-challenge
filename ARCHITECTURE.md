# DOMORA Architecture

Working reference for the code in this repo. The reasoning behind every choice
(and the rejected alternatives) lives in [docs/DOMORA_SPEC.md](docs/DOMORA_SPEC.md) §2–§17.

## Physical tiers

```mermaid
flowchart TB
    subgraph T1["Tier 1 — Leaf nodes"]
        ENV["ESP32-C6 ENV nodes<br/>radar · PIR · BME280 · reeds · leak"]
        FP["ESP32-C6 FLOW/POWER nodes<br/>CT clamps · flow · valves · SSR"]
        PERC["ESP32-S3 PERCEPTION node<br/>on-node audio TinyML — events only"]
    end
    subgraph T2["Tier 2 — Hub (Arduino UNO Q)"]
        LINUX["Linux side: this repo's hub/ runtime<br/>bus · twin · agents · SQLite · dashboard"]
        M33["STM32U585 side: hardware watchdog<br/>+ safety GPIO (copper interlocks)"]
    end
    CLOUD["Tier 3 — optional cloud<br/>encrypted backup + WireGuard relay only<br/>never in the control path"]
    ENV & FP & PERC -->|"MQTT/TLS over Wi-Fi"| LINUX
    LINUX -.-> CLOUD
```

Safety behaviors are **distributed** (leaf reflexes work with the hub dead);
intelligence is **centralized** (the twin needs cross-node context).

## The cognitive loop (implemented in `hub/agents/`)

```mermaid
flowchart LR
    O["observer<br/>validate+ingest"] --> U["understander<br/>fusion → meaning"]
    U --> PR["predictor<br/>roll forward"]
    PR --> PL["planner<br/>action + expected effect"]
    PL --> S{"safety<br/>capability table"}
    S -->|veto| AL["alert"]
    S -->|pass| A["actor<br/>sole path to actuators"]
    A --> V["verifier<br/>expectation vs reality"]
    V -->|confirmed| O
    V -->|deadline missed| R["retry once"] --> V
    V -->|failed| E["escalate + mark asset suspect"]
```

Agents never call each other. They communicate only through:

- **The twin** (`hub/twin/state.py`) — typed points `{value, t, source, confidence}`,
  staleness-aware. Silence is a signal.
- **The bus** (`hub/core/bus.py`) — MQTT-style topics, one contract for
  simulation and production:

| Topic | Direction | Meaning |
|---|---|---|
| `domora/<node>/<asset>/<point>` | node → hub | sensor reading |
| `domora/plan/action` | planner → actor | approved Action (with Expectation) |
| `domora/cmd/<asset>/<command>` | actor → node | actuation |
| `domora/act/dispatched` | actor → verifier | open the verification window |
| `domora/verify/confirmed` | verifier → all | loop closed |
| `domora/alert/<severity>` | anyone → human | veto / escalation |

## The expectation contract (the load-bearing idea)

Every `Action` (see `hub/agents/base.py`) carries an `Expectation`:
a **point**, a **predicate**, a human-readable **describe**, and a
**deadline**. The verifier holds the action open until the predicate is
satisfied by an *independent* sensor or the deadline passes. Outcomes:

- **confirmed** — model and world agree; loop closes silently.
- **retry (once)** — transient failure tolerated exactly once.
- **failed** — asset marked `suspect` in the twin, critical alert raised,
  human takes over. *A stuck valve is discovered the day it sticks.*

## Knowledge graph (`hub/config/house.json`)

Assets + typed edges (`feeds`, `senses`). `graph.upstream_shutoff(asset)`
walks `feeds` edges backwards to find the controllable valve isolating a
leak — causal response is a traversal, not an inference.

## What is deliberately absent

No LLM in the control loop, no RL, no cloud dependency, no per-agent
frameworks. The spec's §25 explains each exclusion; the short version is
that everything in the loop must be explainable after the fact and
functional with the internet cut.

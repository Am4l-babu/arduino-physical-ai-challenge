# The DOMORA Agents — designed to work the way a good agentic assistant works

Each agent owns one cognitive responsibility, the same discipline an agentic
AI assistant applies to software work, mapped onto a physical house:

| Assistant behavior | DOMORA agent | The rule it enforces |
|---|---|---|
| Read before you write; never act on assumption | `observer` | No reading enters the twin unvalidated; rejects are quarantined loudly and become sensor-health signals |
| Think: turn raw data into meaning, with stated confidence | `understander` | Fusion + physics closure. It writes *conclusions with confidence*, e.g. `house.occupied (0.95)` — never raw guesses |
| Look ahead before committing | `predictor` | Rolls the model forward ("tank empty in ~N"), so the planner can pre-act instead of react |
| Plan with success criteria declared up front | `planner` | Every action carries cause, evidence, and a falsifiable **Expectation** with a deadline — the definition of done, written before doing |
| Respect hard limits; some actions are never yours to take | `safety` | Capability table + invariants, deliberately ML-free. `gas_valve:open` isn't refused — it's unrepresentable |
| Act through narrow, auditable interfaces | `actor` | The only code path to actuators; one arbiter per device; journals before dispatch |
| Verify the outcome; never claim unverified success | `verifier` | Confirms via an *independent* sensor, retries exactly once, then fails honestly |
| Escalate clearly when blocked, with evidence | `verifier` | Failure = critical alert + asset marked `suspect` + the full expected-vs-observed record |
| Learn from feedback | (Phase 2) `learner` | Nightly baseline re-fits; user confirm/dismiss on alerts becomes labels |

## Contracts

- Agents **never call each other** — bus + twin only. Any agent can be
  replaced, tested, or run standalone.
- Every message an agent emits is **narrated** with its tick and name; the
  narration log *is* the explainability feature and the demo script.
- An agent that has nothing true to say says nothing (alert budget: trust
  dies by alarm fatigue, not missed detections).

## Adding a new behavior (the checklist)

1. New sensing? Extend `sim/virtual_house.py` first — behavior lands in
   simulation before hardware, always.
2. New meaning? Add a virtual sensor in `hub/twin/virtual_sensors.py` that
   writes evidence, not just a boolean.
3. New action? Add the `(asset, command)` pair to the safety capability
   table **only if** the planner should ever do it autonomously, and give the
   action a real Expectation — if you cannot name the sensor that will verify
   it, the action is not ready to be autonomous.
4. Add a scenario test in `tests/` covering both the success *and* the
   failure path. The stuck-valve test is the template.

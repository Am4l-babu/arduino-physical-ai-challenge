// Derives the "living house" model from raw twin points. Pure functions
// only — screens call these, nothing here touches the DOM. Every field is
// traced to a real point key from the hub contract (docs/APP_PLAN.md §0);
// this file is the one place that mapping lives, so no screen invents state.
import { STATE } from "./format.js";

function get(points, key, dflt) {
  const p = points.get(key);
  return p ? p.value : dflt;
}

export function deriveWater(points) {
  const flowLpm = Number(get(points, "tank.line.flow_lpm", 0)) || 0;
  const levelPct = Number(get(points, "water_tank.level_pct", NaN));
  const valveState = get(points, "main_valve.valve_state", "—");
  const pumpState = get(points, "pump.pump_state", "—");
  const pumpCurrentA = Number(get(points, "pump.current_a", NaN));
  const leak = !!get(points, "virtual.water.leak_suspected", false);
  const dryrun = !!get(points, "virtual.pump.dryrun_suspected", false);
  const valveSuspect = get(points, "health.main_valve") === "suspect";
  const pumpSuspect = get(points, "health.pump") === "suspect";

  let state = STATE.OK;
  if (leak || valveSuspect) state = STATE.CRIT;
  else if (dryrun || pumpSuspect) state = STATE.CRIT;
  else if (!Number.isNaN(levelPct) && levelPct < 15) state = STATE.WARN;

  return { flowLpm, levelPct, valveState, pumpState, pumpCurrentA, leak, dryrun, valveSuspect, pumpSuspect, state };
}

export function deriveOccupancy(points) {
  const occupied = !!get(points, "house.occupied", false);
  const pir = !!get(points, "living.pir", false);
  const radar = !!get(points, "living.radar", false);
  return { occupied, pir, radar };
}

export function derivePower(points) {
  const totalW = Number(get(points, "main_panel.power_w", NaN));
  return { totalW };
}

// NILM ledger note: this was originally reconstructed client-side by
// pattern-matching nilm.<name>.* twin points. That turned out to be
// unsound — hub/agents/energy.py's label_nearest() renames a cluster by
// copying its points to the new name but (correctly, per hub/twin/state.py's
// "silence is itself a signal, points are never deleted" design) never
// retires the old "clusterN.*" ones. A settled, legitimately-unchanging
// ledger entry (an appliance that finished its cycle) and an orphaned
// pre-relabel ghost are indistinguishable by staleness alone — found by
// feeding this a real captured run and getting a phantom 4th appliance,
// then over-correcting and losing kettle too. The ledger now comes from
// GET /nilm (core/nilm.js), which calls the same energy.report() the
// server already trusts (hub/agents/energy.py, proven in tests/test_nilm.py)
// instead of re-deriving it from an ambiguous point shape.

// Zones shown on the Live Home hero. Each maps to a slice of the model
// above plus the state token that colors it — the "health color" language
// from docs/APP_PLAN.md §1.
export function deriveZones(points) {
  const water = deriveWater(points);
  const occ = deriveOccupancy(points);
  const power = derivePower(points);

  return [
    { id: "living", label: "Living", state: STATE.OK, detail: occ.occupied ? "occupied" : "empty" },
    { id: "utility", label: "Water / Utility", state: water.state, detail: waterDetail(water) },
    { id: "panel", label: "Main Panel", state: STATE.OK, detail: Number.isNaN(power.totalW) ? "—" : `${power.totalW.toFixed(0)} W` },
  ];
}

function waterDetail(water) {
  if (water.leak) return "leak suspected";
  if (water.dryrun) return "pump dry-run";
  if (water.valveSuspect) return "valve suspect";
  return "nominal";
}

// Overall house health = the worst zone. Drives the ambient shell glow.
export function overallState(zones) {
  const order = [STATE.CRIT, STATE.WARN, STATE.LEARN, STATE.PRED, STATE.OK];
  for (const s of order) if (zones.some((z) => z.state === s)) return s;
  return STATE.OK;
}

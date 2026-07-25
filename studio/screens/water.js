// Phase 3 — Water dashboard. Flow, tank level, valve/pump state, leak +
// dry-run status, and the real incident list (the flagship leak-loop and
// dry-run-protection actions, reused from the live action ledger — the
// same data the app-wide scrub-back playback already replays, so a second
// bespoke scrubber isn't built here; see docs/APP_PLAN.md §4 Phase 3).
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { deriveWater } from "../core/twin.js";
import { fmtNum, fmtPct, STATE } from "../core/format.js";
import { statTile } from "../ui/stat-tile.js";
import { healthDot, chip } from "../ui/health-dot.js";
import { lineChart } from "../ui/line-chart.js";
import { fetchHistory } from "../core/history.js";

const LEVEL_KEY = "water_tank.level_pct";
const FLOW_KEY = "tank.line.flow_lpm";

let unsubscribe = null;
let journal = { level: null, flow: null };

export function renderWater(target) {
  if (unsubscribe) unsubscribe();
  journal = { level: null, flow: null };

  const paint = raf(() => mount(target, view(store.state)));
  paint();
  unsubscribe = store.subscribe(paint);

  fetchHistory(LEVEL_KEY).then((s) => { journal.level = s; paint(); });
  fetchHistory(FLOW_KEY).then((s) => { journal.flow = s; paint(); });
}

function view(state) {
  const points = state.points;
  const water = deriveWater(points);
  const hasWater = water.valveState !== "—" || !Number.isNaN(water.levelPct) || water.flowLpm > 0;

  if (!hasWater) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Water"),
      h("div", { class: "empty" }, "This scenario doesn't run the water system. Try --scenario leak, stuck, dryrun, or dryrun_stuck."),
    ]);
  }

  const levelSeries = (journal.level && journal.level.length) ? journal.level : store.series(LEVEL_KEY);
  const flowSeries = (journal.flow && journal.flow.length) ? journal.flow : store.series(FLOW_KEY);

  return h("div", { class: "water-screen" }, [
    h("div", { class: "vitals-rail" }, [
      statTile({ label: "Line flow", value: fmtNum(water.flowLpm, 2), unit: "L/min", state: water.leak ? STATE.CRIT : "" }),
      statTile({ label: "Tank level", value: fmtPct(water.levelPct), state: water.levelPct < 15 ? STATE.WARN : "" }),
      statTile({ label: "Main valve", value: water.valveState, state: water.valveSuspect ? STATE.CRIT : "" }),
      statTile({ label: "Pump", value: water.pumpState, state: water.pumpSuspect || water.dryrun ? STATE.CRIT : "" }),
    ]),

    h("div", { class: "water-status-row" }, [
      chip(water.leak ? "leak suspected" : "no leak", water.leak ? STATE.CRIT : STATE.OK),
      chip(water.dryrun ? "pump dry-run suspected" : "pump nominal", water.dryrun ? STATE.CRIT : STATE.OK),
      chip(water.valveSuspect ? "valve suspect" : "valve trusted", water.valveSuspect ? STATE.CRIT : STATE.OK),
    ]),

    h("div", { class: "grid two-col" }, [
      h("div", { class: "glass card" }, [
        h("h2", {}, "Tank level — this session"),
        lineChart({ data: levelSeries, unit: "%", valueFmt: (v) => v.toFixed(0) }),
        journal.level ? h("div", { class: "chart-note" }, "Journal-backed (recorded run).") : null,
      ]),
      h("div", { class: "glass card" }, [
        h("h2", {}, "Line flow — this session"),
        lineChart({ data: flowSeries, unit: " L/min", valueFmt: (v) => v.toFixed(2) }),
        journal.flow ? h("div", { class: "chart-note" }, "Journal-backed (recorded run).") : null,
      ]),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Incidents — cause → evidence → command → verify"),
      state.actionOrder.length
        ? h("div", { class: "incident-list" }, state.actionOrder.map((id) => incidentRow(state.actions.get(id))))
        : h("div", { class: "empty" }, "No autonomous action yet in this run."),
    ]),
  ]);
}

function incidentRow(a) {
  const statusChip = a.status === "confirmed" ? chip("verified", STATE.OK)
    : a.status === "failed" ? chip("escalated", STATE.CRIT)
    : chip("pending", STATE.LEARN);
  return h("div", { class: "incident-row" }, [
    h("div", { class: "incident-head" }, [
      healthDot(a.status === "confirmed" ? STATE.OK : a.status === "failed" ? STATE.CRIT : STATE.LEARN),
      h("span", { class: "incident-cause" }, a.cause || `action #${a.id}`),
      statusChip,
    ]),
    h("div", { class: "incident-detail" }, [
      h("span", {}, `command: ${a.command || "—"}`),
      h("span", {}, `expect: ${a.expect || "—"}`),
      a.retries ? h("span", {}, `retried ${a.retries}×`) : null,
      a.reason ? h("span", { class: "incident-reason" }, a.reason) : null,
    ]),
  ]);
}

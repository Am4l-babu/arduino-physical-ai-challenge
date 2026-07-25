// Phase 1 — Live Home: the hero screen. Every element below is bound to a
// real twin point or cognition event; nothing here is decorative filler.
// See docs/APP_PLAN.md §4 Phase 1 for the binding list and §5 for the
// observable definition of done.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { deriveWater, deriveOccupancy, derivePower, deriveZones, overallState } from "../core/twin.js";
import { fmtNum, fmtPct, fmtWatts, fmtTick, STATE } from "../core/format.js";
import { statTile } from "../ui/stat-tile.js";
import { healthDot, chip } from "../ui/health-dot.js";
import { navigate } from "../core/router.js";

let unsubscribe = null;

export function renderHome(target) {
  if (unsubscribe) unsubscribe();
  const paint = raf(() => mount(target, view(store.state)));
  paint();
  unsubscribe = store.subscribe(paint);
}

function view(state) {
  const points = state.points;
  const water = deriveWater(points);
  const occ = deriveOccupancy(points);
  const power = derivePower(points);
  const zones = deriveZones(points);
  const overall = overallState(zones);
  const latestAction = state.actionOrder.length ? state.actions.get(state.actionOrder[0]) : null;

  return h("div", { class: "home" }, [
    h("div", { class: `glass card home-hero ${overall}` }, [
      h("div", { class: "hero-row" }, [
        h("div", {}, [
          h("h2", {}, "The house, right now"),
          h("div", { class: "hero-state" }, [
            healthDot(overall),
            h("span", {}, overallLabel(overall)),
            h("span", { class: "hero-t" }, fmtTick(state.now)),
          ]),
        ]),
        chip(occ.occupied ? "occupied" : "empty", occ.occupied ? STATE.OK : STATE.LEARN),
      ]),
      h("div", { class: "zone-grid" }, zones.map(zoneCard)),
    ]),

    h("div", { class: "vitals-rail" }, [
      statTile({ label: "Occupancy", value: occ.occupied ? "Home" : "Away", state: occ.occupied ? STATE.OK : "" }),
      statTile({ label: "Line flow", value: fmtNum(water.flowLpm, 2), unit: "L/min", state: water.leak ? STATE.CRIT : "" }),
      statTile({ label: "Tank level", value: fmtPct(water.levelPct), state: water.levelPct < 15 ? STATE.WARN : "" }),
      statTile({ label: "Main valve", value: water.valveState, state: water.valveSuspect ? STATE.CRIT : water.valveState === "closed" ? "" : STATE.OK }),
      statTile({ label: "Pump", value: water.pumpState, state: water.pumpSuspect || water.dryrun ? STATE.CRIT : water.pumpState === "on" ? STATE.OK : "" }),
      statTile({ label: "Power draw", value: fmtWatts(power.totalW) }),
    ]),

    h("div", { class: "glass card thinking-strip" }, [
      h("h2", {}, "The house is thinking"),
      latestAction ? actionLine(latestAction) : h("div", { class: "empty" }, "No autonomous action yet — the house is watching."),
    ]),
  ]);
}

function overallLabel(state) {
  return { [STATE.OK]: "Nominal", [STATE.WARN]: "Attention", [STATE.CRIT]: "Critical", [STATE.LEARN]: "Learning", [STATE.PRED]: "Predicting" }[state] || "Nominal";
}

function zoneCard(zone) {
  return h("div", { class: `zone-card ${zone.state}`, onclick: () => navigate(`/room/${zone.id}`) }, [
    healthDot(zone.state),
    h("div", { class: "zone-label" }, zone.label),
    h("div", { class: "zone-detail" }, zone.detail),
  ]);
}

function actionLine(a) {
  const statusChip = a.status === "confirmed"
    ? chip("verified", STATE.OK)
    : a.status === "failed"
      ? chip("escalated", STATE.CRIT)
      : chip("pending", STATE.LEARN);
  return h("div", { class: "action-line" }, [
    h("span", { class: "cause" }, a.cause || `action #${a.id}`),
    h("span", { class: "arrow" }, "→"),
    h("span", { class: "expect" }, a.expect || a.command || ""),
    statusChip,
  ]);
}

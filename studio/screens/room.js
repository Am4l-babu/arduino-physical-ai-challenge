// Phase 4 — Room detail page. One page per real zone from core/twin.js's
// deriveZones() (living / utility / panel — the only zones this system
// actually has data for). Shows real points, the real action/incident
// timeline where one genuinely applies to the zone, and health. No 3D view,
// predictions, automation, or maintenance suggestions — none of that is
// computed anywhere in this codebase yet; see docs/APP_PLAN.md §7.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { deriveZones, deriveWater, deriveOccupancy, derivePower } from "../core/twin.js";
import { navigate } from "../core/router.js";
import { fmt, STATE } from "../core/format.js";
import { healthDot, chip } from "../ui/health-dot.js";
import { lineChart } from "../ui/line-chart.js";

const ZONES = {
  living: {
    label: "Living",
    pointKeys: ["house.occupied", "living.pir", "living.radar"],
    chartKey: null,
    actionsRelevant: false,
  },
  utility: {
    label: "Water / Utility",
    pointKeys: [
      "tank.line.flow_lpm", "water_tank.level_pct", "main_valve.valve_state",
      "pump.pump_state", "pump.current_a", "virtual.water.leak_suspected",
      "virtual.pump.dryrun_suspected", "health.main_valve", "health.pump",
    ],
    chartKey: "water_tank.level_pct",
    actionsRelevant: true,
  },
  panel: {
    label: "Main Panel",
    pointKeys: ["main_panel.power_w"],
    chartKey: "main_panel.power_w",
    actionsRelevant: false,
  },
};

let unsubscribe = null;

export function renderRoom(target, params) {
  if (unsubscribe) unsubscribe();
  const paint = raf(() => mount(target, view(store.state, params.id)));
  paint();
  unsubscribe = store.subscribe(paint);
}

function view(state, id) {
  const zoneDef = ZONES[id];
  if (!zoneDef) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Unknown room"),
      h("div", { class: "empty" }, `No zone named "${id}". Try Living, Utility, or Panel from the Home screen.`),
    ]);
  }

  const zones = deriveZones(state.points);
  const zone = zones.find((z) => zoneDef.label === z.label) || { state: STATE.OK, detail: "—" };
  const water = deriveWater(state.points);
  const occ = deriveOccupancy(state.points);
  const power = derivePower(state.points);

  return h("div", { class: "room-screen" }, [
    h("div", { class: `glass card room-header ${zone.state}` }, [
      healthDot(zone.state),
      h("div", {}, [
        h("h1", { class: "room-title" }, zoneDef.label),
        h("div", { class: "room-detail" }, zone.detail),
      ]),
    ]),

    zoneDef.chartKey ? h("div", { class: "glass card" }, [
      h("h2", {}, "Trend — this session"),
      lineChart({ data: store.series(zoneDef.chartKey), valueFmt: (v) => v.toFixed(1) }),
    ]) : null,

    id === "living" ? h("div", { class: "glass card" }, [
      h("h2", {}, "Occupancy"),
      h("div", { class: "occ-row" }, [
        chip(occ.occupied ? "occupied" : "empty", occ.occupied ? STATE.OK : STATE.LEARN),
        h("span", { class: "room-mini" }, `radar ${occ.radar ? "on" : "off"} · PIR ${occ.pir ? "on" : "off"}`),
      ]),
    ]) : null,

    id === "utility" ? h("div", { class: "water-status-row" }, [
      chip(water.leak ? "leak suspected" : "no leak", water.leak ? STATE.CRIT : STATE.OK),
      chip(water.dryrun ? "pump dry-run" : "pump nominal", water.dryrun ? STATE.CRIT : STATE.OK),
    ]) : null,

    id === "panel" && !Number.isNaN(power.totalW)
      ? h("div", { class: "glass card" }, [h("h2", {}, "Power now"), h("div", { class: "room-power" }, `${power.totalW.toFixed(0)} W`)])
      : null,

    h("div", { class: "glass card" }, [
      h("h2", {}, "Points in this room"),
      pointsList(state, zoneDef.pointKeys),
    ]),

    zoneDef.actionsRelevant ? h("div", { class: "glass card" }, [
      h("h2", {}, "Autonomous actions in this room"),
      state.actionOrder.length
        ? h("div", { class: "incident-list" }, state.actionOrder.map((aid) => actionRow(state.actions.get(aid))))
        : h("div", { class: "empty" }, "No autonomous action yet in this run."),
    ]) : h("div", { class: "glass card" }, [
      h("h2", {}, "Autonomous actions"),
      h("div", { class: "empty" }, "This system never acts on this room — only the water loop (utility) is autonomous today."),
    ]),
  ]);
}

function pointsList(state, keys) {
  const rows = keys.map((key) => {
    const p = state.points.get(key);
    return h("div", { class: "sensor-row", onclick: () => navigate(`/sensor/${encodeURIComponent(key)}`) }, [
      h("span", { class: "sensor-key" }, key),
      h("span", { class: "sensor-value" }, p ? fmt(p.value) : "—"),
      h("span", { class: "sensor-arrow" }, "›"),
    ]);
  });
  return h("div", { class: "sensor-list" }, rows);
}

function actionRow(a) {
  const statusChip = a.status === "confirmed" ? chip("verified", STATE.OK)
    : a.status === "failed" ? chip("escalated", STATE.CRIT)
    : chip("pending", STATE.LEARN);
  return h("div", { class: "incident-row" }, [
    h("div", { class: "incident-head" }, [
      healthDot(a.status === "confirmed" ? STATE.OK : a.status === "failed" ? STATE.CRIT : STATE.LEARN),
      h("span", { class: "incident-cause" }, a.cause || `action #${a.id}`),
      statusChip,
    ]),
  ]);
}

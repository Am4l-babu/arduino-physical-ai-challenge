// Phase 4 — Appliance detail page. Data comes from GET /nilm (core/nilm.js
// fetches the summary; here we also need per-cluster mean_w/events, so this
// screen calls /nilm directly for the full report) — the same authoritative
// hub/agents/energy.py ledger used everywhere else in Studio. Health score,
// sound/vibration analysis, remaining-useful-life, and failure probability
// are NOT computed anywhere in this codebase — this page says so rather
// than inventing numbers. See docs/APP_PLAN.md §7.
import { h, mount } from "../core/dom.js";
import { fmtWatts } from "../core/format.js";

const POLL_MS = 2000;
let intervalId = null;

export function renderAppliance(target, params) {
  if (intervalId) clearInterval(intervalId);
  const name = params.name;

  const load = () => fetchReport().then((report) => mount(target, view(name, report)));
  load();
  intervalId = setInterval(load, POLL_MS);
}

async function fetchReport() {
  try {
    const res = await fetch("/nilm");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function view(name, report) {
  if (!report) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Appliance"),
      h("div", { class: "empty" }, "No NILM data available — this scenario doesn't run the panel CT, or the hub isn't reachable."),
    ]);
  }
  const cluster = report.clusters.find((c) => c.label === name);
  const energyWh = report.energy_wh[name];

  if (!cluster && energyWh == null) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Appliance"),
      h("div", { class: "empty" }, `No appliance named "${name}" in the current NILM ledger.`),
    ]);
  }

  return h("div", { class: "appliance-screen" }, [
    h("div", { class: "glass card appliance-header" }, [
      h("h1", { class: "appliance-title" }, name),
      h("div", { class: "appliance-sub" }, cluster ? `signature ${cluster.mean_w} W` : "signature unknown"),
    ]),

    h("div", { class: "vitals-rail" }, [
      statTileLike("Energy this run", energyWh != null ? `${energyWh.toFixed(2)} Wh` : "—"),
      statTileLike("Signature power", cluster ? fmtWatts(cluster.mean_w) : "—"),
      statTileLike("On/off events", cluster ? String(cluster.events) : "—"),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Not computed"),
      h("div", { class: "not-connected-list" }, [
        notComputedRow("Health score"),
        notComputedRow("Remaining useful life"),
        notComputedRow("Failure probability"),
        notComputedRow("Sound / vibration analysis"),
      ]),
      h("p", { class: "appliance-note" },
        "This system disaggregates appliances from the panel's aggregate power alone (NILM). It doesn't have per-appliance current, sound, or vibration sensors, so it has no basis to compute these — showing a number here would be invented, not measured."),
    ]),
  ]);
}

function statTileLike(label, value) {
  return h("div", { class: "glass stat-tile" }, [
    h("span", { class: "k" }, label),
    h("span", { class: "v" }, value),
  ]);
}

function notComputedRow(label) {
  return h("div", { class: "not-connected-row" }, [
    h("span", { class: "nc-dot" }),
    h("span", {}, label),
    h("span", { class: "nc-note" }, "not computed"),
  ]);
}

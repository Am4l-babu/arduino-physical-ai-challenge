// Phase 4 — Sensor detail page. Generic: works for any twin point key,
// because every point in this system already carries the same shape
// {value, t, source, confidence} (hub/twin/state.py's Point). No per-sensor
// calibration UI — nothing in the backend exposes calibration to change,
// so building that control would be decorative. See docs/APP_PLAN.md §7.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { fmt, fmtTick, STATE } from "../core/format.js";
import { chip } from "../ui/health-dot.js";
import { lineChart } from "../ui/line-chart.js";
import { fetchHistory } from "../core/history.js";

const STALE_AFTER = 15; // matches hub/twin/state.py's STALE_AFTER

let unsubscribe = null;
let journalSeries = null;
let lastKey = null;

export function renderSensor(target, params) {
  if (unsubscribe) unsubscribe();
  const key = params.key;
  if (key !== lastKey) { journalSeries = null; lastKey = key; }

  const paint = raf(() => mount(target, view(store.state, key)));
  paint();
  unsubscribe = store.subscribe(paint);

  fetchHistory(key).then((series) => { journalSeries = series; paint(); });
}

function view(state, key) {
  const p = state.points.get(key);
  if (!p) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Sensor"),
      h("div", { class: "empty" }, `No live data for "${key}" yet in this run.`),
    ]);
  }

  const age = state.now - p.t;
  const stale = age > STALE_AFTER;
  const isNumeric = typeof p.value === "number";
  const series = isNumeric ? ((journalSeries && journalSeries.length) ? journalSeries : store.series(key)) : [];

  return h("div", { class: "sensor-screen" }, [
    h("div", { class: "glass card sensor-header" }, [
      h("h1", { class: "sensor-title" }, key),
      chip(stale ? "stale" : "live", stale ? STATE.WARN : STATE.OK),
    ]),

    h("div", { class: "vitals-rail" }, [
      statTileLike("Value", fmt(p.value)),
      statTileLike("Source", p.source || "—"),
      statTileLike("Confidence", p.confidence != null ? p.confidence.toFixed(2) : "—"),
      statTileLike("Age", `${age} tick${age === 1 ? "" : "s"}`),
    ]),

    isNumeric ? h("div", { class: "glass card" }, [
      h("h2", {}, "Trend"),
      lineChart({ data: series }),
      journalSeries ? h("div", { class: "chart-note" }, "Journal-backed (recorded run).") : null,
    ]) : null,

    h("div", { class: "glass card" }, [
      h("h2", {}, "Recent raw values"),
      series.length
        ? h("table", { class: "sensor-table" }, [
            h("thead", {}, [h("tr", {}, [h("th", {}, "t"), h("th", {}, "value")])]),
            h("tbody", {}, series.slice(-15).reverse().map((pt) =>
              h("tr", {}, [h("td", {}, fmtTick(pt.t)), h("td", {}, fmt(pt.value))]))),
          ])
        : h("div", { class: "empty" }, isNumeric ? "No history recorded yet." : "This point isn't numeric — no trend/history table to show, just the live value above."),
    ]),
  ]);
}

function statTileLike(label, value) {
  return h("div", { class: "glass stat-tile" }, [
    h("span", { class: "k" }, label),
    h("span", { class: "v" }, value),
  ]);
}

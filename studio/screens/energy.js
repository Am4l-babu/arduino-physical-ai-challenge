// Phase 3 — Energy dashboard. Live power (from /ws twin points) + the real
// NILM ledger (from GET /nilm — the server's own authoritative report, see
// core/nilm.js), plus a trend chart: journal-backed when the server was
// started with --playback, otherwise the live session buffer
// (core/store.js's series()). No fabricated thresholds or forecasts —
// see docs/APP_PLAN.md §7.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { derivePower } from "../core/twin.js";
import { fmtWatts } from "../core/format.js";
import { statTile } from "../ui/stat-tile.js";
import { lineChart } from "../ui/line-chart.js";
import { barChart } from "../ui/bar-chart.js";
import { fetchHistory } from "../core/history.js";
import { fetchNilm } from "../core/nilm.js";
import { navigate } from "../core/router.js";

const POWER_KEY = "main_panel.power_w";
const NILM_POLL_MS = 2000;

let unsubscribe = null;
let intervalId = null;
let journalSeries = null; // null = not loaded yet / unavailable this run
let nilm = [];

export function renderEnergy(target) {
  if (unsubscribe) unsubscribe();
  if (intervalId) clearInterval(intervalId);
  journalSeries = null;
  nilm = [];

  const paint = raf(() => mount(target, view(store.state)));
  paint();
  unsubscribe = store.subscribe(paint);

  fetchHistory(POWER_KEY).then((series) => { journalSeries = series; paint(); });

  const pollNilm = () => fetchNilm().then((report) => { if (report) { nilm = report; paint(); } });
  pollNilm();
  intervalId = setInterval(pollNilm, NILM_POLL_MS);
}

function view(state) {
  const points = state.points;
  const power = derivePower(points);
  const series = (journalSeries && journalSeries.length) ? journalSeries : store.series(POWER_KEY);

  if (Number.isNaN(power.totalW) && !nilm.length) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "Energy"),
      h("div", { class: "empty" }, "This scenario doesn't report whole-house power. Run the hub with --scenario energy to see this dashboard live."),
    ]);
  }

  const peak = series.length ? Math.max(...series.map((p) => p.value)) : power.totalW;
  const nearPeak = !Number.isNaN(power.totalW) && peak > 0 && power.totalW >= peak * 0.9;

  return h("div", { class: "energy-screen" }, [
    h("div", { class: "vitals-rail" }, [
      statTile({ label: "Power now", value: Number.isNaN(power.totalW) ? "—" : fmtWatts(power.totalW),
                state: nearPeak ? "st-warn" : "" }),
      statTile({ label: "Session peak", value: series.length ? fmtWatts(peak) : "—" }),
      statTile({ label: "Appliances tracked", value: String(nilm.length) }),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Power — this session"),
      lineChart({ data: series, unit: " W", valueFmt: (v) => v.toFixed(0) }),
      journalSeries ? h("div", { class: "chart-note" }, "Journal-backed (recorded run).") : null,
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "NILM appliance breakdown"),
      nilm.length
        ? barChart({
            items: nilm.map((a) => ({ label: a.name, value: a.energyWh })), unit: " Wh",
            onItemClick: (item) => navigate(`/appliance/${encodeURIComponent(item.label)}`),
          })
        : h("div", { class: "empty" }, "No appliance edges detected yet — the disaggregator needs a device to switch on/off."),
    ]),
  ]);
}

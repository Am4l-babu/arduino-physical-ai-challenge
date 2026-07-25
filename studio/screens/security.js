// Phase 3 — Security dashboard. Real data only: occupancy fusion (radar +
// PIR -> house.occupied) and the real alert feed. Door/window/motion/gas/
// smoke sensors have no simulator or hardware feeding the twin yet (no
// scenario in sim/ publishes them) — rather than fabricate widgets for
// them, this screen says so plainly. See docs/APP_PLAN.md §7.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { deriveOccupancy } from "../core/twin.js";
import { fmtTick, STATE } from "../core/format.js";
import { healthDot, chip } from "../ui/health-dot.js";

const NOT_CONNECTED = ["Doors / windows", "Motion (beyond living-room radar+PIR)", "Glass break", "Smoke", "Gas"];

let unsubscribe = null;

export function renderSecurity(target) {
  if (unsubscribe) unsubscribe();
  const paint = raf(() => mount(target, view(store.state)));
  paint();
  unsubscribe = store.subscribe(paint);
}

function view(state) {
  const occ = deriveOccupancy(state.points);
  const alerts = state.feed.filter((f) => f.topic.startsWith("domora/alert"));

  return h("div", { class: "security-screen" }, [
    h("div", { class: "glass card" }, [
      h("h2", {}, "Occupancy"),
      h("div", { class: "occ-row" }, [
        chip(occ.occupied ? "occupied" : "empty", occ.occupied ? STATE.OK : STATE.LEARN),
        h("span", { class: "occ-detail" }, `radar ${occ.radar ? "on" : "off"} · PIR ${occ.pir ? "on" : "off"}`),
      ]),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Alerts"),
      alerts.length
        ? h("div", { class: "alert-list" }, alerts.map(alertRow))
        : h("div", { class: "empty" }, "No alerts in this run."),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Not yet connected"),
      h("div", { class: "not-connected-list" }, NOT_CONNECTED.map((label) =>
        h("div", { class: "not-connected-row" }, [
          h("span", { class: "nc-dot" }),
          h("span", {}, label),
          h("span", { class: "nc-note" }, "no node reporting this yet"),
        ]))),
    ]),
  ]);
}

function alertRow(f) {
  const reason = f.payload && f.payload.reason;
  return h("div", { class: "alert-row" }, [
    healthDot(STATE.CRIT),
    h("span", { class: "alert-t" }, fmtTick(f.t)),
    h("span", { class: "alert-topic" }, f.topic),
    reason ? h("span", { class: "alert-reason" }, reason) : null,
  ]);
}

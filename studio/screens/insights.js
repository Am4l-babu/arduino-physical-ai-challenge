// Phase 5 — AI Insights: prioritized observation cards, not a raw
// notification feed. See core/insights.js for what each card traces back to.
import { h, mount, raf } from "../core/dom.js";
import { store } from "../core/store.js";
import { deriveInsights } from "../core/insights.js";
import { fetchNilm } from "../core/nilm.js";
import { chip, healthDot } from "../ui/health-dot.js";
import { STATE } from "../core/format.js";

const NILM_POLL_MS = 3000;
const PRIORITY_STATE = { critical: STATE.CRIT, warning: STATE.WARN, info: STATE.LEARN };
const PRIORITY_LABEL = { critical: "Critical", warning: "Warning", info: "Info" };

let unsubscribe = null;
let intervalId = null;
let nilm = [];

export function renderInsights(target) {
  if (unsubscribe) unsubscribe();
  if (intervalId) clearInterval(intervalId);
  nilm = [];

  const paint = raf(() => mount(target, view(store.state)));
  paint();
  unsubscribe = store.subscribe(paint);

  const poll = () => fetchNilm().then((r) => { if (r) { nilm = r; paint(); } });
  poll();
  intervalId = setInterval(poll, NILM_POLL_MS);
}

function view(state) {
  const cards = deriveInsights(state, nilm);
  const groups = ["critical", "warning", "info"]
    .map((p) => ({ priority: p, items: cards.filter((c) => c.priority === p) }))
    .filter((g) => g.items.length);

  return h("div", { class: "insights-screen" }, groups.map((g) =>
    h("div", { class: "glass card" }, [
      h("h2", {}, [chip(PRIORITY_LABEL[g.priority], PRIORITY_STATE[g.priority]), ` (${g.items.length})`]),
      h("div", { class: "insight-list" }, g.items.map((c) => insightCard(c, g.priority))),
    ])));
}

function insightCard(card, priority) {
  return h("div", { class: "insight-row" }, [
    healthDot(PRIORITY_STATE[priority]),
    h("span", { class: "insight-text" }, card.text),
  ]);
}

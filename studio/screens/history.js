// Phase 5 — History: scrub a recorded journal (GET /playback.json, only
// present when the server was started with --playback demo.db). Keeps its
// own local reconstructed state rather than touching the live store
// singleton, so scrubbing the past never corrupts what Home/Water/Energy
// show as "now" if the user switches tabs mid-scrub.
import { h, mount } from "../core/dom.js";
import { fmt, fmtTick, STATE } from "../core/format.js";
import { chip, healthDot } from "../ui/health-dot.js";

const PLAY_INTERVAL_MS = 200;

let target = null;
let timeline = [];
let tMax = 0;
let t = 0;
let playing = false;
let timer = null;

export function renderHistory(mountTarget) {
  target = mountTarget;
  stop();
  timeline = []; tMax = 0; t = 0;
  paint("loading");

  fetch("/playback.json")
    .then((res) => (res.ok ? res.json() : Promise.reject()))
    .then((data) => {
      timeline = data.timeline || [];
      tMax = data.t_max || 0;
      t = tMax; // land on the resolved end-state; scrub back to watch it unfold
      paint();
    })
    .catch(() => paint("unavailable"));
}

function paint(mode) {
  if (!target) return;
  mount(target, view(mode));
}

function reconstructAt(tick) {
  const points = new Map();
  const actions = new Map();
  const actionOrder = [];
  for (const f of timeline) {
    if (f.t > tick) break; // JournalReader.timeline() is sorted by t
    if (f.type === "point") {
      points.set(f.key, { value: f.value, t: f.t, source: f.source, confidence: f.confidence });
    } else if (f.type === "event") {
      const payload = f.payload || {};
      const a = payload.action;
      if ((f.topic === "domora/plan/action" || f.topic === "domora/act/dispatched") && a) {
        let m = actions.get(a.id);
        if (!m) { m = { id: a.id, status: "pending" }; actions.set(a.id, m); actionOrder.unshift(a.id); }
        m.cause = a.cause; m.command = a.command_topic; m.evidence = a.evidence;
        if (a.expectation) m.expect = a.expectation.describe;
      } else if (f.topic === "domora/verify/confirmed" && actions.has(payload.action_id)) {
        actions.get(payload.action_id).status = "confirmed";
      } else if (f.topic.startsWith("domora/alert") && actions.has(payload.action_id)) {
        Object.assign(actions.get(payload.action_id), { status: "failed", reason: payload.reason });
      }
    }
  }
  return { points, actions, actionOrder };
}

function seek(tick) {
  t = Math.max(0, Math.min(tMax, tick));
  paint();
}

function stop() {
  playing = false;
  if (timer) clearInterval(timer);
  timer = null;
}

function play() {
  if (t >= tMax) seek(0);
  playing = true;
  timer = setInterval(() => {
    if (t >= tMax) { stop(); paint(); return; }
    seek(t + 1);
  }, PLAY_INTERVAL_MS);
  paint();
}

function view(mode) {
  if (mode === "loading") {
    return h("div", { class: "glass card" }, [h("h2", {}, "History"), h("div", { class: "empty" }, "Loading recorded journal…")]);
  }
  if (mode === "unavailable" || !timeline.length) {
    return h("div", { class: "glass card" }, [
      h("h2", {}, "History"),
      h("div", { class: "empty" },
        "No recorded journal for this run. Home, Water, Energy, and Security already show what's happening now. " +
        "To browse history: run the hub with --journal demo.db, then serve it with " +
        "`python -m hub.services.api --playback demo.db`."),
    ]);
  }

  const { points, actions, actionOrder } = reconstructAt(t);
  const keys = [...points.keys()].sort();

  return h("div", { class: "history-screen" }, [
    h("div", { class: "glass card history-scrubber" }, [
      h("div", { class: "history-controls" }, [
        h("button", { type: "button", class: "history-play", onclick: () => (playing ? stop() : play()) }, playing ? "❚❚ Pause" : "▶ Play"),
        h("input", {
          type: "range", min: 0, max: tMax, value: t, class: "history-range",
          oninput: (e) => { stop(); seek(Number(e.target.value)); },
        }),
        h("span", { class: "history-t" }, `${fmtTick(t)} / ${fmtTick(tMax)}`),
      ]),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Actions at this point"),
      actionOrder.length
        ? h("div", { class: "incident-list" }, actionOrder.map((id) => actionRow(actions.get(id))))
        : h("div", { class: "empty" }, "No action dispatched yet at this tick."),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Points at this point"),
      h("table", { class: "sensor-table" }, [
        h("thead", {}, [h("tr", {}, [h("th", {}, "key"), h("th", {}, "value")])]),
        h("tbody", {}, keys.map((k) => h("tr", {}, [h("td", {}, k), h("td", {}, fmt(points.get(k).value))]))),
      ]),
    ]),
  ]);
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

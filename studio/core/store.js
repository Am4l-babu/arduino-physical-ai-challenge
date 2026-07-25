// The live twin state model. One store, filled by socket.js, read by every
// screen. Not a generic framework store — shaped directly around the three
// message types the hub actually emits (snapshot / point / event), see
// docs/APP_PLAN.md §0.

const HISTORY_LIMIT = 500;
const FEED_LIMIT = 80;
const SERIES_LIMIT = 300; // per key — this session only; see docs/APP_PLAN.md §7

function createStore() {
  const state = {
    connection: "connecting", // connecting | live | down
    now: 0,
    points: new Map(),        // key -> {value, t, source, confidence}
    series: new Map(),        // key -> [{t, value}, …] — bounded, numeric points only, this session
    actions: new Map(),       // id -> {id, cause, evidence, command, expect, status, retries, reason}
    actionOrder: [],          // most-recent-first ids
    feed: [],                 // recent {topic, payload, t}, most-recent-first
    scenario: null,
  };

  const listeners = new Set();
  function notify() { for (const fn of listeners) fn(state); }

  return {
    state,
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },

    setConnection(status) { state.connection = status; notify(); },

    applySnapshot(msg) {
      state.now = msg.t || 0;
      state.points = new Map(Object.entries(msg.points || {}));
      for (const [key, p] of state.points) this._pushSeries(key, p.t, p.value);
      notify();
    },

    applyPoint(msg) {
      state.now = msg.t ?? state.now;
      state.points.set(msg.key, { value: msg.value, t: msg.t, source: msg.source, confidence: msg.confidence });
      this._pushSeries(msg.key, msg.t, msg.value);
      notify();
    },

    _pushSeries(key, t, value) {
      if (typeof value !== "number" || !Number.isFinite(value)) return;
      let arr = state.series.get(key);
      if (!arr) { arr = []; state.series.set(key, arr); }
      if (arr.length && arr[arr.length - 1].t === t) { arr[arr.length - 1].value = value; return; }
      arr.push({ t, value });
      if (arr.length > SERIES_LIMIT) arr.shift();
    },

    series(key) {
      return state.series.get(key) || [];
    },

    applyEvent(msg) {
      state.now = msg.t ?? state.now;
      state.feed.unshift({ topic: msg.topic, payload: msg.payload, t: msg.t });
      if (state.feed.length > FEED_LIMIT) state.feed.length = FEED_LIMIT;

      const payload = msg.payload || {};
      const a = payload.action;
      if ((msg.topic === "domora/plan/action" || msg.topic === "domora/act/dispatched") && a) {
        this._upsertAction(a);
      } else if (msg.topic === "domora/verify/confirmed") {
        this._markAction(payload.action_id, "confirmed");
      } else if (msg.topic.startsWith("domora/alert") && payload.action_id != null) {
        this._markAction(payload.action_id, "failed", { reason: payload.reason });
      }
      notify();
    },

    _upsertAction(a) {
      let m = state.actions.get(a.id);
      if (!m) {
        m = { id: a.id, status: "pending" };
        state.actions.set(a.id, m);
        state.actionOrder.unshift(a.id);
        if (state.actionOrder.length > HISTORY_LIMIT) state.actionOrder.length = HISTORY_LIMIT;
      }
      m.cause = a.cause ?? m.cause;
      m.command = a.command_topic ?? m.command;
      m.evidence = a.evidence ?? m.evidence;
      if (a.expectation) m.expect = a.expectation.describe;
      if (a.retries != null) m.retries = a.retries;
    },

    _markAction(id, status, extra) {
      let m = state.actions.get(id);
      if (!m) { m = { id, status: "pending" }; state.actions.set(id, m); state.actionOrder.unshift(id); }
      m.status = status;
      if (extra) Object.assign(m, extra);
    },

    point(key, dflt = undefined) {
      const p = state.points.get(key);
      return p ? p.value : dflt;
    },

    reset() {
      state.now = 0; state.points = new Map(); state.series = new Map(); state.actions = new Map();
      state.actionOrder = []; state.feed = [];
      notify();
    },
  };
}

export const store = createStore();

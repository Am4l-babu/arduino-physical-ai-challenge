// Phase 5 — Settings: read-first, minimal, per docs/APP_PLAN.md. House and
// Nodes come from the real house knowledge graph (GET /graph, hub/config/
// house.json). AI lists the intents hub/services/ai_query.py actually
// implements. Users is honest: this system has no accounts/roles yet.
import { h, mount } from "../core/dom.js";

const AI_INTENTS = [
  "Power / energy — “why is power high?”",
  "Leak status — “is there a leak?”",
  "Appliance health — “which appliance is unhealthy?”",
  "Water usage (needs --journal) — “how much water was used?”",
  "What changed while away (needs --journal)",
  "House status overview",
];

export function renderSettings(target) {
  mount(target, view("loading"));
  fetch("/graph")
    .then((res) => (res.ok ? res.json() : Promise.reject()))
    .then((data) => mount(target, view("ok", data)))
    .catch(() => mount(target, view("unavailable")));
}

function view(mode, data) {
  return h("div", { class: "settings-screen" }, [
    h("div", { class: "glass card" }, [
      h("h2", {}, "House"),
      mode === "ok"
        ? h("div", { class: "settings-summary" }, roomList(data.assets))
        : h("div", { class: "empty" }, mode === "loading" ? "Loading…" : "House graph not available from this server."),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Nodes / assets"),
      mode === "ok" ? assetTable(data.assets) : h("div", { class: "empty" }, mode === "loading" ? "Loading…" : "—"),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "AI"),
      h("p", { class: "settings-note" }, "DOMORA AI answers are deterministic and grounded in the real twin/NILM/journal — no LLM in this build. What you can ask:"),
      h("ul", { class: "settings-list" }, AI_INTENTS.map((t) => h("li", {}, t))),
    ]),

    h("div", { class: "glass card" }, [
      h("h2", {}, "Users"),
      h("div", { class: "empty" }, "Single-user. No accounts, roles, or login are implemented yet — anyone reaching this server has full access. Don't expose it beyond a trusted network."),
    ]),
  ]);
}

function roomList(assets) {
  const rooms = [...new Set(assets.map((a) => a.room))].sort();
  return h("div", { class: "room-chip-row" }, rooms.map((r) => h("span", { class: "chip" }, r)));
}

function assetTable(assets) {
  return h("table", { class: "sensor-table" }, [
    h("thead", {}, [h("tr", {}, [h("th", {}, "id"), h("th", {}, "type"), h("th", {}, "room"), h("th", {}, "commands")])]),
    h("tbody", {}, assets.map((a) =>
      h("tr", {}, [
        h("td", {}, a.id), h("td", {}, a.type), h("td", {}, a.room),
        h("td", {}, (a.commands || []).join(", ") || "—"),
      ]))),
  ]);
}

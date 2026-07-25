// The global command bar (⌘K / Ctrl+K): search screens, rooms, and live
// twin points, then navigate. Deliberately search-and-navigate only — it
// does NOT issue commands. This system's only actuation path is the
// planner dispatching through hub/agents/safety.py's capability table;
// adding a manual "type a command, it runs" surface would be a new
// safety-relevant capability, and CLAUDE.md requires an explicit invariant
// review for capability-table changes. That's a decision for the project
// owner, not something to slip in via a search box. See docs/APP_PLAN.md §7.
import { h, mount } from "../core/dom.js";
import { store } from "../core/store.js";
import { navigate } from "../core/router.js";

const SCREENS = [
  { label: "Home", path: "/home" },
  { label: "DOMORA AI", path: "/ai" },
  { label: "Energy", path: "/energy" },
  { label: "Water", path: "/water" },
  { label: "Security", path: "/security" },
  { label: "History", path: "/history" },
  { label: "AI Insights", path: "/insights" },
  { label: "Settings", path: "/settings" },
];
const ROOMS = [
  { label: "Room: Living", path: "/room/living" },
  { label: "Room: Water / Utility", path: "/room/utility" },
  { label: "Room: Main Panel", path: "/room/panel" },
];

let open = false;
let query = "";
let overlayEl = null;

export function mountCommandBar(root) {
  overlayEl = h("div", { class: "cmdbar-overlay", onclick: () => setOpen(false) });
  root.appendChild(overlayEl);
  paint();

  const isBrowser = typeof window !== "undefined" && typeof window.addEventListener === "function";
  if (isBrowser) {
    window.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen(!open);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    });
  }
}

export function isOpen() { return open; }
export function openCommandBar() { setOpen(true); }

function setOpen(next) {
  open = next;
  if (!open) query = "";
  paint();
  if (open && overlayEl.querySelector) {
    const input = overlayEl.querySelector("#cmdbar-input");
    if (input && input.focus) input.focus();
  }
}

function results() {
  const q = query.trim().toLowerCase();
  const screens = SCREENS.filter((s) => !q || s.label.toLowerCase().includes(q)).map((s) => ({ ...s, hint: "screen" }));
  const rooms = ROOMS.filter((r) => !q || r.label.toLowerCase().includes(q)).map((r) => ({ ...r, hint: "room" }));
  const points = [...store.state.points.keys()]
    .filter((k) => q && k.toLowerCase().includes(q)) // points only show once you type — the full point list is long
    .slice(0, 8)
    .map((k) => ({ label: k, path: `/sensor/${encodeURIComponent(k)}`, hint: "point" }));
  return [...screens, ...rooms, ...points].slice(0, 12);
}

function paint() {
  if (!overlayEl) return;
  overlayEl.setAttribute("class", `cmdbar-overlay${open ? " on" : ""}`);
  mount(overlayEl, open ? panel() : h("div"));
}

function panel() {
  const items = results();
  return h("div", { class: "cmdbar-panel glass", onclick: (e) => e.stopPropagation() }, [
    h("input", {
      id: "cmdbar-input", class: "cmdbar-input", type: "text", placeholder: "Search screens, rooms, points…",
      value: query, autocomplete: "off",
      oninput: (e) => { query = e.target.value; paint(); },
    }),
    h("div", { class: "cmdbar-results" }, items.length
      ? items.map(resultRow)
      : h("div", { class: "empty" }, query ? "No matches." : "Type to search, or pick a screen below.")),
  ]);
}

function resultRow(item) {
  return h("div", { class: "cmdbar-row", onclick: () => { navigate(item.path); setOpen(false); } }, [
    h("span", { class: "cmdbar-hint" }, item.hint),
    h("span", { class: "cmdbar-label" }, item.label),
  ]);
}

// Boot: build the app shell, wire the router, connect the live socket.
// No build step, no bundler — plain ES modules loaded by the browser.
import { h, mount, raf } from "./core/dom.js";
import { store } from "./core/store.js";
import { boot as bootSocket } from "./core/socket.js";
import { register, registerFallback, start, onRouteChange } from "./core/router.js";
import { fmtTick } from "./core/format.js";
import { renderHome } from "./screens/home.js";
import { renderAI } from "./screens/ai.js";
import { renderEnergy } from "./screens/energy.js";
import { renderWater } from "./screens/water.js";
import { renderSecurity } from "./screens/security.js";
import { renderRoom } from "./screens/room.js";
import { renderAppliance } from "./screens/appliance.js";
import { renderSensor } from "./screens/sensor.js";
import { renderHistory } from "./screens/history.js";
import { renderInsights } from "./screens/insights.js";
import { renderSettings } from "./screens/settings.js";
import { mountCommandBar, openCommandBar } from "./ui/command-bar.js";

const NAV = [
  { path: "/home", label: "Home", ready: true },
  { path: "/ai", label: "AI", ready: true },
  { path: "/energy", label: "Energy", ready: true },
  { path: "/water", label: "Water", ready: true },
  { path: "/security", label: "Security", ready: true },
  { path: "/history", label: "History", ready: true },
  { path: "/insights", label: "Insights", ready: true },
  { path: "/settings", label: "Settings", ready: true },
];

function shell() {
  const statusDot = h("span", { class: "status-dot", id: "status-dot" });
  const statusText = h("span", { id: "status-text" }, "connecting…");
  const clock = h("span", { id: "clock" }, "t=000");
  const viewEl = h("main", { class: "view", id: "view" });
  const tabsEl = h("nav", { class: "tabs", id: "tabs" }, NAV.map(navLink));

  const root = h("div", {}, [
    h("header", { class: "topbar" }, [
      h("div", { class: "brand" }, [h("span", { class: "mark" }, "DOMORA"), h("span", { class: "sub" }, "Studio")]),
      tabsEl,
      h("button", { type: "button", class: "cmdbar-trigger", onclick: () => openCommandBar() }, "⌘K"),
      h("div", { class: "status-pill" }, [statusDot, statusText, clock]),
    ]),
    viewEl,
    h("div", { class: "footnote" }, "DOMORA supplements, and never replaces, certified life-safety detectors."),
  ]);

  return { root, statusDot, statusText, clock, viewEl, tabsEl };
}

function navLink(item) {
  if (!item.ready) return h("span", { class: "chip", style: "opacity:.5;cursor:default" }, `${item.label} · soon`);
  return h("a", { href: `#${item.path}`, "data-path": item.path }, item.label);
}

function main() {
  const { root, statusDot, statusText, clock, viewEl, tabsEl } = shell();
  mount(document.getElementById("app"), root);

  register("/home", renderHome);
  register("/ai", renderAI);
  register("/energy", renderEnergy);
  register("/water", renderWater);
  register("/security", renderSecurity);
  register("/room/:id", renderRoom);
  register("/appliance/:name", renderAppliance);
  register("/sensor/:key", renderSensor);
  register("/history", renderHistory);
  register("/insights", renderInsights);
  register("/settings", renderSettings);
  registerFallback(renderHome);
  onRouteChange((path) => {
    for (const a of tabsEl.querySelectorAll("a")) a.classList.toggle("active", a.dataset.path === path);
  });
  start(viewEl);

  const paintChrome = raf((state) => {
    statusDot.className = "status-dot " + (state.connection === "live" ? "live" : state.connection === "down" ? "down" : "");
    statusText.textContent = state.connection === "live" ? "live" : state.connection === "down" ? "reconnecting…" : "connecting…";
    clock.textContent = fmtTick(state.now);
  });
  store.subscribe(paintChrome);
  paintChrome(store.state);

  mountCommandBar(document.body);
  bootSocket();
}

main();

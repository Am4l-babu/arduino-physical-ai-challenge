import { h } from "../core/dom.js";

export function statTile({ label, value, unit, state }) {
  return h("div", { class: "glass stat-tile" }, [
    h("span", { class: "k" }, label),
    h("span", { class: `v ${state || ""}`.trim() }, value),
    unit ? h("span", { class: "u" }, unit) : null,
  ]);
}

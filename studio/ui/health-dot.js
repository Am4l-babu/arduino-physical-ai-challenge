import { h } from "../core/dom.js";

export function healthDot(state) {
  return h("span", { class: `health-dot ${state || "st-ok"}` });
}

export function chip(text, state) {
  return h("span", { class: `chip ${state || ""}`.trim() }, text);
}

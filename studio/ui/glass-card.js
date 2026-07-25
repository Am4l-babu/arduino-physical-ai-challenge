import { h } from "../core/dom.js";

export function glassCard({ title, className = "" } = {}, children = []) {
  return h("section", { class: `glass card ${className}`.trim() }, [
    title ? h("h2", {}, title) : null,
    ...([].concat(children)),
  ]);
}

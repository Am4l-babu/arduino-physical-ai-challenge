// A small horizontal categorical bar chart — the NILM appliance breakdown.
// Each bar is already named by its direct label, so identity isn't
// color-alone even without a separate legend box (see .claude/skills/dataviz
// choosing-a-form.md). Caller passes items pre-sorted (largest first).
import { h } from "../core/dom.js";

const CAT = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)"];

export function barChart({ items, width = 480, valueFmt, unit = "", onItemClick }) {
  if (!items || !items.length) {
    return h("div", { class: "chart-empty" }, "No data yet.");
  }
  const fmt = valueFmt || ((v) => v.toFixed(2));
  const max = Math.max(...items.map((i) => i.value), 0.001);
  const rowH = 28, gap = 10, barH = 18;
  const labelW = 96;
  const trackW = width - labelW - 56;
  const height = items.length * (rowH + gap) - gap;

  const rows = items.map((item, i) => {
    const barW = Math.max(2, (item.value / max) * trackW);
    const color = CAT[i % CAT.length];
    const rowY = i * (rowH + gap);
    const props = { transform: `translate(0,${rowY})` };
    if (onItemClick) { props.class = "chart-bar-row-clickable"; props.onclick = () => onItemClick(item); }
    return h("g", props, [
      h("text", { x: labelW - 8, y: rowH / 2 + 4, class: "chart-bar-label", "text-anchor": "end" }, item.label),
      h("rect", { x: labelW, y: (rowH - barH) / 2, width: trackW, height: barH, rx: 4, class: "chart-bar-track" }),
      h("rect", { x: labelW, y: (rowH - barH) / 2, width: barW, height: barH, rx: 4, fill: color, class: "chart-bar-fill" }),
      h("text", { x: labelW + barW + 8, y: rowH / 2 + 4, class: "chart-bar-value" }, `${fmt(item.value)}${unit}`),
    ]);
  });

  return h("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg chart-bar-svg" }, rows);
}

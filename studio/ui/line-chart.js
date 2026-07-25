// A single-series trend chart (line + 10%-opacity area, hairline grid,
// end label, hover crosshair+tooltip). Sequential color job, one hue — see
// .claude/skills/dataviz. Hover state lives in local DOM mutation, not the
// outer store-driven re-render, so mouse tracking stays smooth even while
// the screen around it keeps repainting from live data.
import { h } from "../core/dom.js";

const PAD = { top: 10, right: 12, bottom: 20, left: 44 };

export function lineChart({ data, width = 480, height = 160, color = "var(--seq)", unit = "", valueFmt }) {
  const fmt = valueFmt || ((v) => v.toFixed(1));
  if (!data || data.length < 2) {
    return h("div", { class: "chart-empty" }, "Not enough data yet — the trend needs a few more ticks.");
  }

  const w = width - PAD.left - PAD.right;
  const plotH = height - PAD.top - PAD.bottom;
  const ts = data.map((d) => d.t);
  const vs = data.map((d) => d.value);
  const tMin = Math.min(...ts), tMax = Math.max(...ts);
  const vMin = Math.min(0, ...vs);
  const vMax = Math.max(...vs, vMin + 1) * 1.08;

  const x = (t) => PAD.left + (tMax === tMin ? 0 : ((t - tMin) / (tMax - tMin)) * w);
  const y = (v) => PAD.top + plotH - ((v - vMin) / (vMax - vMin || 1)) * plotH;

  const linePath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(d.t).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ");
  const baseY = (PAD.top + plotH).toFixed(1);
  const areaPath = `${linePath} L${x(ts[ts.length - 1]).toFixed(1)},${baseY} L${x(ts[0]).toFixed(1)},${baseY} Z`;

  const gridLines = [0, 0.5, 1].map((f) => {
    const gy = PAD.top + plotH * f;
    const val = vMax - (vMax - vMin) * f;
    return h("g", {}, [
      h("line", { x1: PAD.left, x2: width - PAD.right, y1: gy, y2: gy, class: "chart-grid" }),
      h("text", { x: PAD.left - 8, y: gy + 4, class: "chart-axis-label", "text-anchor": "end" }, fmt(val)),
    ]);
  });

  const last = data[data.length - 1];
  const endDot = h("circle", { cx: x(last.t), cy: y(last.value), r: 4, class: "chart-end-dot", fill: color });
  const endLabel = h("text", {
    x: Math.min(x(last.t) + 6, width - PAD.right - 4), y: Math.max(y(last.value) - 8, PAD.top + 10),
    class: "chart-end-label",
  }, `${fmt(last.value)}${unit}`);

  const crosshair = h("line", { class: "chart-crosshair", x1: 0, x2: 0, y1: PAD.top, y2: PAD.top + plotH, visibility: "hidden" });
  const hoverDot = h("circle", { r: 4, class: "chart-hover-dot", fill: color, visibility: "hidden" });
  const ttT = h("text", { class: "chart-tooltip-t", x: 6, y: 14 }, "");
  const ttV = h("text", { class: "chart-tooltip-v", x: 6, y: 28 }, "");
  const tooltip = h("g", { class: "chart-tooltip", visibility: "hidden" }, [
    h("rect", { class: "chart-tooltip-bg", rx: 4, width: 76, height: 34 }),
    ttT, ttV,
  ]);

  function onMove(evt) {
    const rect = evt.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const svgX = (evt.clientX - rect.left) * (width / rect.width);
    const frac = Math.min(1, Math.max(0, (svgX - PAD.left) / w));
    const idx = Math.round(frac * (data.length - 1));
    const d = data[idx];
    if (!d) return;
    const cx = x(d.t), cy = y(d.value);
    crosshair.setAttribute("x1", cx); crosshair.setAttribute("x2", cx); crosshair.setAttribute("visibility", "visible");
    hoverDot.setAttribute("cx", cx); hoverDot.setAttribute("cy", cy); hoverDot.setAttribute("visibility", "visible");
    const tx = Math.min(cx + 8, width - PAD.right - 76);
    const ty = Math.max(PAD.top, cy - 40);
    tooltip.setAttribute("transform", `translate(${tx},${ty})`);
    tooltip.setAttribute("visibility", "visible");
    ttT.textContent = `t=${d.t}`;
    ttV.textContent = `${fmt(d.value)}${unit}`;
  }
  function onLeave() {
    crosshair.setAttribute("visibility", "hidden");
    hoverDot.setAttribute("visibility", "hidden");
    tooltip.setAttribute("visibility", "hidden");
  }

  return h("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart-svg", onmousemove: onMove, onmouseleave: onLeave }, [
    ...gridLines,
    h("path", { d: areaPath, class: "chart-area", fill: color }),
    h("path", { d: linePath, class: "chart-line", stroke: color, fill: "none" }),
    endDot, endLabel,
    crosshair, hoverDot, tooltip,
  ]);
}

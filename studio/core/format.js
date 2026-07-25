// Formatting helpers shared by every screen. No locale/timezone guessing —
// the hub speaks in sim ticks (t) today; wall-clock formatting is added
// when a real node stream carries wall-clock timestamps.

export function fmtNum(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toFixed(digits);
}

export function fmtPct(v, digits = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Number(v).toFixed(digits)}%`;
}

export function fmtTick(t) {
  return `t=${String(t ?? 0).padStart(3, "0")}`;
}

export function fmtWatts(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return v >= 1000 ? `${(v / 1000).toFixed(2)} kW` : `${Number(v).toFixed(0)} W`;
}

// The five-color health vocabulary (see docs/APP_PLAN.md §1). Screens map
// domain state into one of these tokens; nothing invents its own palette.
export const STATE = Object.freeze({ OK: "st-ok", WARN: "st-warn", CRIT: "st-crit", LEARN: "st-learn", PRED: "st-pred" });

export function fmt(v) {
  if (v == null) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function escapeHtml(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

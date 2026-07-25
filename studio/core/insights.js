// AI Insights — observation cards derived from real twin/action state, not
// raw notifications forwarded as-is. Every card here traces to a signal
// already shown elsewhere in Studio (leak/dry-run/health/tank/NILM/action
// outcomes); this is a different, prioritized presentation of real state,
// not a new inference engine. See docs/APP_PLAN.md §4 Phase 5.
function get(points, key, dflt) {
  const p = points.get(key);
  return p ? p.value : dflt;
}

export function deriveInsights(state, nilm) {
  const points = state.points;
  const cards = [];

  if (get(points, "virtual.water.leak_suspected", false)) {
    const ev = get(points, "virtual.water.leak_evidence", {}) || {};
    cards.push({
      id: "leak", priority: "critical",
      text: `Leak suspected on the main line: ${ev.flow_lpm ?? "?"} L/min flowing with the house empty, persistent for ${ev.persisted_ticks ?? "?"} ticks.`,
      evidence: ev,
    });
  }

  if (get(points, "virtual.pump.dryrun_suspected", false)) {
    const ev = get(points, "virtual.pump.dryrun_evidence", {}) || {};
    cards.push({
      id: "dryrun", priority: "critical",
      text: `Pump dry-run suspected: drawing ${ev.pump_current_a ?? "?"} A while the tank level isn't rising.`,
      evidence: ev,
    });
  }

  for (const [key, p] of points) {
    if (key.startsWith("health.") && p.value === "suspect") {
      const asset = key.slice("health.".length);
      cards.push({
        id: `health-${asset}`, priority: "warning",
        text: `${asset.replace(/_/g, " ")} is flagged suspect by an independent sensor, not just a timed-out command.`,
        evidence: { asset },
      });
    }
  }

  const level = Number(get(points, "water_tank.level_pct", NaN));
  if (!Number.isNaN(level) && level < 15) {
    cards.push({
      id: "tank-low", priority: "warning",
      text: `Tank level is low: ${level.toFixed(0)}%.`,
      evidence: { level_pct: level },
    });
  }

  for (const id of state.actionOrder) {
    const a = state.actions.get(id);
    if (a.status === "failed") {
      cards.push({
        id: `action-failed-${a.id}`, priority: "critical",
        text: `Action "${a.cause}" escalated: ${a.reason || "verification failed"}.`,
        evidence: { action_id: a.id, command: a.command },
      });
    } else if (a.status === "pending" && a.retries > 0) {
      cards.push({
        id: `action-retry-${a.id}`, priority: "warning",
        text: `Action "${a.cause}" has been retried ${a.retries}× and is still pending.`,
        evidence: { action_id: a.id },
      });
    }
  }

  if (nilm && nilm.length) {
    const top = nilm[0];
    cards.push({
      id: "nilm-top", priority: "info",
      text: `${top.name} used the most energy this session: ${top.energyWh.toFixed(2)} Wh.`,
      evidence: { appliance: top.name, energy_wh: top.energyWh },
    });
  }

  if (!cards.length) {
    cards.push({ id: "nominal", priority: "info", text: "Nothing to flag — the house reads nominal.", evidence: {} });
  }

  const order = { critical: 0, warning: 1, info: 2 };
  return cards.sort((a, b) => order[a.priority] - order[b.priority]);
}

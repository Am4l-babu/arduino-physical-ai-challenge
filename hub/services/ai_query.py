"""DOMORA AI — grounded query engine (docs/APP_PLAN.md §4 Phase 2).

Deterministic and offline: no LLM, no network, no dependency the UNO Q
might not have at the venue. Every number in an answer is pulled straight
from the twin, the NILM ledger, or the SQLite journal — never invented.
`llm_adapter.py` may later rephrase this same evidence into freer language;
it must never become the source of the numbers.

A handful of intents are matched by keyword, not real NLU — that is a
deliberate, honest scope choice (see docs/APP_PLAN.md §7): a templated
answer over real data beats a fluent answer over guessed data.
"""

import json
import re
from dataclasses import dataclass, field


@dataclass
class Answer:
    text: str
    evidence: dict = field(default_factory=dict)
    intent: str = "unknown"


class AIQuery:
    """Answers questions against one hub world: twin (+ optional NILM agent
    and read-only journal). Construct fresh per request; it holds no state
    of its own beyond the references handed in.
    """

    def __init__(self, twin, energy=None, journal=None):
        self.twin = twin
        self.energy = energy      # hub.agents.energy.EnergySense, for the NILM ledger
        self.journal = journal    # hub.services.store.JournalReader, already opened

    def ask(self, message: str) -> Answer:
        text = (message or "").lower()
        for pattern, handler in self._ROUTES:
            if pattern.search(text):
                return handler(self)
        return self._unknown()

    # --- intents -----------------------------------------------------------

    def _leak(self) -> Answer:
        suspected = bool(self.twin.get("virtual.water.leak_suspected", False))
        valve = self.twin.get("main_valve.valve_state", "unknown")
        if not suspected:
            return Answer(f"No leak suspected right now. Main valve is {valve}.",
                          evidence={"leak_suspected": False, "valve_state": valve}, intent="leak")
        ev = self.twin.get("virtual.water.leak_evidence", {}) or {}
        return Answer(
            f"Yes — a leak is suspected: {ev.get('flow_lpm', '?')} L/min flowing with "
            f"{ev.get('fixtures_open', '?')} fixtures open and nobody home, persistent for "
            f"{ev.get('persisted_ticks', '?')} ticks. Main valve is currently {valve}.",
            evidence={"leak_suspected": True, "valve_state": valve, **ev}, intent="leak")

    def _health(self) -> Answer:
        snapshot = self.twin.snapshot()
        suspects = sorted(k[len("health."):] for k, v in snapshot.items()
                          if k.startswith("health.") and v == "suspect")
        if not suspects:
            return Answer("Everything is reading healthy — no asset is currently flagged suspect.",
                          evidence={"suspects": []}, intent="health")
        verb = "is" if len(suspects) == 1 else "are"
        return Answer(
            f"{', '.join(suspects)} {verb} currently flagged suspect by an independent sensor "
            "— not just a command that timed out.",
            evidence={"suspects": suspects}, intent="health")

    def _power(self) -> Answer:
        watts = self.twin.get("main_panel.power_w")
        if watts is None:
            return Answer("I don't have a live power reading right now.", intent="power")
        report = self.energy.report() if self.energy else {"clusters": [], "energy_wh": {}}
        ledger = report.get("energy_wh", {})
        if not ledger:
            return Answer(
                f"The house is drawing {watts:.0f} W right now. I haven't disaggregated any "
                "individual appliances yet — that needs a few on/off cycles first.",
                evidence={"power_w": watts}, intent="power")
        ranked = sorted(ledger.items(), key=lambda kv: -kv[1])
        top_name, top_wh = ranked[0]
        breakdown = ", ".join(f"{name} {wh:.2f} Wh" for name, wh in ranked)
        clusters = report.get("clusters", [])
        unlabelled = [c for c in clusters if c["label"].startswith("cluster")]
        note = (f" ({len(unlabelled)} cluster{'s' if len(unlabelled) != 1 else ''} still "
                "unlabelled — the dashboard's 'what just turned on?' flow names them)"
                if unlabelled else "")
        return Answer(
            f"Right now the house draws {watts:.0f} W. The biggest contributor so far is "
            f"{top_name} at {top_wh:.2f} Wh. Full breakdown: {breakdown}.{note}",
            evidence={"power_w": watts, "energy_wh": ledger}, intent="power")

    def _water_usage(self) -> Answer:
        if self.journal is None:
            flow = self.twin.get("tank.line.flow_lpm")
            return Answer(
                "I don't have a recorded journal for this run, so the best I can give you is "
                f"the live line flow: {flow if flow is not None else '—'} L/min. Historical "
                "totals need a run started with `--journal`.",
                evidence={"flow_lpm": flow}, intent="water_usage")
        liters, t0, t1 = self._integrate_flow()
        return Answer(
            f"Over the recorded run (t={t0} to t={t1} — this system tracks simulation ticks "
            "right now, not calendar days, so 'yesterday' isn't meaningful yet), about "
            f"{liters:.1f} liters passed through the main line.",
            evidence={"liters": liters, "t_start": t0, "t_end": t1}, intent="water_usage")

    def _away(self) -> Answer:
        if self.journal is None:
            return Answer(
                "I don't have a recorded journal for this run, so I can't replay what happened "
                "while you were away.", intent="away")
        timeline = self.journal.timeline()
        cognitive = ("domora/alert", "domora/act", "domora/plan", "domora/verify")
        away_events = [f for f in timeline if f["type"] == "event"
                       and f["topic"].startswith(cognitive)
                       and not self._occupied_at(timeline, f["t"])]
        if not away_events:
            return Answer("Nothing notable happened while the house was empty.",
                          evidence={"events": []}, intent="away")
        lines = [f"t={f['t']}: {f['topic']}" for f in away_events[:10]]
        return Answer("While you were away: " + "; ".join(lines),
                      evidence={"events": away_events[:10]}, intent="away")

    def _simulation(self) -> Answer:
        return Answer(
            "Running what-if simulations from chat isn't wired up yet — that's a named Phase-2 "
            "item in docs/APP_PLAN.md, handed off to a sim scenario rather than answered here.",
            intent="simulation_not_implemented")

    def _status(self) -> Answer:
        occ = self.twin.get("house.occupied", False)
        valve = self.twin.get("main_valve.valve_state", "unknown")
        watts = self.twin.get("main_panel.power_w")
        parts = [f"House is {'occupied' if occ else 'empty'}", f"main valve {valve}"]
        if watts is not None:
            parts.append(f"drawing {watts:.0f} W")
        return Answer(", ".join(parts) + ".",
                      evidence={"occupied": occ, "valve_state": valve, "power_w": watts},
                      intent="status")

    def _unknown(self) -> Answer:
        return Answer(
            "I don't have data to answer that yet — try asking about power, water, leaks, "
            "appliance health, what changed while you were away, or the house's overall status.",
            intent="unknown")

    # --- helpers -------------------------------------------------------

    def _integrate_flow(self):
        rows = list(self.journal.db.execute(
            "SELECT t, value FROM points_journal WHERE key='tank.line.flow_lpm' ORDER BY t"))
        if not rows:
            return 0.0, 0, 0
        liters = 0.0
        prev_t = None
        for t, value in rows:
            lpm = json.loads(value)
            if prev_t is not None:
                liters += lpm * (t - prev_t) / 60.0  # L/min over dt seconds -> liters
            prev_t = t
        return liters, rows[0][0], rows[-1][0]

    def _occupied_at(self, timeline, t) -> bool:
        occ = False
        for f in timeline:
            if f["t"] > t:
                break
            if f["type"] == "point" and f["key"] == "house.occupied":
                occ = bool(f["value"])
        return occ

    _ROUTES = [
        (re.compile(r"\bleaks?\b"), _leak),
        (re.compile(r"unhealthy|health|maintenance|failing|degrad"), _health),
        (re.compile(r"while.*away|what changed|while.*out"), _away),
        (re.compile(r"simulat|what if|what (will|would) happen"), _simulation),
        (re.compile(r"water.*(used|usage|consum)|how much water"), _water_usage),
        (re.compile(r"power|energy|consumption|watt|kwh"), _power),
        (re.compile(r"status|overview|how is the house|what's going on|summary"), _status),
    ]

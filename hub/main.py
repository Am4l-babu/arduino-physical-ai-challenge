"""DOMORA hub orchestrator.

Wires the twin, the knowledge graph and the seven agents onto one bus and
runs the closed loop against the virtual house.

    python -m hub.main --scenario leak    # valve works: loop closes, verified
    python -m hub.main --scenario stuck   # valve jammed: verification fails,
                                          # retry, escalate — the flagship demo

No broker, no hardware, no dependencies: the same agents that will run on
the UNO Q run here against simulated physics.
"""

import argparse
from pathlib import Path

from hub.agents.actor import Actor
from hub.agents.energy import EnergySense
from hub.agents.observer import Observer
from hub.agents.planner import Planner
from hub.agents.predictor import Predictor
from hub.agents.safety import Safety
from hub.agents.understander import Understander
from hub.agents.verifier import Verifier
from hub.core.bus import EventBus
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState
from sim.virtual_house import VirtualHouse
from sim.virtual_loads import VirtualLoads

HOUSE_CONFIG = Path(__file__).parent / "config" / "house.json"


def run(scenario: str = "leak", ticks: int = 120, quiet: bool = False,
        journal_db: str = None) -> dict:
    bus = EventBus()
    twin = TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)

    store = None
    if journal_db:
        from hub.services.store import Store
        store = Store(journal_db)
        store.attach(bus, twin)

    lines = []

    def narrate(t: int, agent: str, message: str) -> None:
        line = f"[t={t:03d}] {agent:<12} | {message}"
        lines.append(line)
        if not quiet:
            print(line)

    alerts = []
    bus.subscribe("domora/alert/#", lambda topic, p: alerts.append({"topic": topic, **p}))

    if scenario == "energy":
        house = VirtualLoads(bus)
    else:
        house = VirtualHouse(bus, stuck_valve=(scenario == "stuck"))

    ctx = (bus, twin, graph, narrate)
    observer = Observer(*ctx)          # noqa: F841  (event-driven, no tick)
    safety = Safety(*ctx)
    actor = Actor(*ctx)
    understander = Understander(*ctx)
    predictor = Predictor(*ctx)
    planner = Planner(*ctx, safety=safety)
    verifier = Verifier(*ctx, actor=actor)
    energy = EnergySense(*ctx)

    ticking = [understander, predictor, planner, verifier, energy]

    if not quiet:
        print(f"--- DOMORA closed-loop run · scenario: {scenario} ---")
    for t in range(ticks):
        twin.now = t
        house.tick(t)
        for agent in ticking:
            agent.tick(t)
        if scenario == "energy" and t == 75:
            # the interactive-labelling flow: user answers "what was that 1.8 kW?"
            energy.label_nearest(1800, "kettle")

    summary = {
        "scenario": scenario,
        "confirmed": [a.id for a in verifier.confirmed],
        "failed": [a.id for a in verifier.failed],
        "alerts": alerts,
        "valve_commands": getattr(house, "commands_received", []),
        "final_flow_lpm": twin.get("tank.line.flow_lpm"),
        "suspect_assets": [k for k, v in twin.snapshot().items()
                           if k.startswith("health.") and v == "suspect"],
        "narration": lines,
    }
    if store is not None:
        summary["journal"] = store.close()
    if scenario == "energy":
        summary["nilm"] = energy.report()
    if not quiet:
        print("--- summary ---")
        for key in ("confirmed", "failed", "final_flow_lpm", "suspect_assets"):
            print(f"{key}: {summary[key]}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the DOMORA closed loop against the virtual house")
    parser.add_argument("--scenario", choices=["leak", "stuck", "energy"], default="leak")
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--journal", metavar="DB", default=None,
                        help="SQLite file to journal twin changes + actions into")
    args = parser.parse_args()
    run(scenario=args.scenario, ticks=args.ticks, journal_db=args.journal)

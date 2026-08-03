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
from types import SimpleNamespace
from typing import Callable

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
from sim.virtual_comfort import VirtualComfort
from sim.virtual_house import VirtualHouse
from sim.virtual_loads import VirtualLoads
from sim.virtual_pump import VirtualPump

HOUSE_CONFIG = Path(__file__).parent / "config" / "house.json"


def wire(scenario: str, narrate: Callable[[int, str, str], None],
         journal_db: str = None) -> SimpleNamespace:
    """Build one fully-wired world (bus, twin, agents, house).

    The single source of truth for how the hub is assembled, shared by the
    batch runner (`run`) and the live dashboard server (`hub.services.api`).
    """
    bus = EventBus()
    twin = TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)

    store = None
    if journal_db:
        from hub.services.store import Store
        store = Store(journal_db)
        store.attach(bus, twin)

    alerts = []
    bus.subscribe("domora/alert/#", lambda topic, p: alerts.append({"topic": topic, **p}))

    if scenario == "energy":
        house = VirtualLoads(bus)
    elif scenario in ("dryrun", "dryrun_stuck"):
        house = VirtualPump(bus, stuck_relay=(scenario == "dryrun_stuck"))
    elif scenario in ("comfort", "comfort_blind"):
        house = VirtualComfort(bus, ir_blind=(scenario == "comfort_blind"))
    else:
        house = VirtualHouse(bus, stuck_valve=(scenario == "stuck"))

    ctx = (bus, twin, graph, narrate)
    observer = Observer(*ctx)          # event-driven: kept alive by its bus subscription
    safety = Safety(*ctx)
    actor = Actor(*ctx)
    understander = Understander(*ctx)
    predictor = Predictor(*ctx)
    planner = Planner(*ctx, safety=safety)
    verifier = Verifier(*ctx, actor=actor)
    energy = EnergySense(*ctx)

    ticking = [understander, predictor, planner, verifier, energy]

    return SimpleNamespace(
        scenario=scenario, bus=bus, twin=twin, graph=graph, store=store,
        alerts=alerts, house=house, ticking=ticking, observer=observer,
        verifier=verifier, energy=energy,
    )


def step(world: SimpleNamespace, t: int) -> None:
    """Advance one tick of an already-wired world."""
    world.twin.now = t
    world.house.tick(t)
    for agent in world.ticking:
        agent.tick(t)
    if world.scenario == "energy" and t == 75:
        # the interactive-labelling flow: user answers "what was that 1.8 kW?"
        world.energy.label_nearest(1800, "kettle")


def run(scenario: str = "leak", ticks: int = 120, quiet: bool = False,
        journal_db: str = None) -> dict:
    lines = []

    def narrate(t: int, agent: str, message: str) -> None:
        line = f"[t={t:03d}] {agent:<12} | {message}"
        lines.append(line)
        if not quiet:
            print(line)

    world = wire(scenario, narrate, journal_db)

    if not quiet:
        print(f"--- DOMORA closed-loop run · scenario: {scenario} ---")
    for t in range(ticks):
        step(world, t)

    summary = {
        "scenario": scenario,
        "confirmed": [a.id for a in world.verifier.confirmed],
        "failed": [a.id for a in world.verifier.failed],
        "alerts": world.alerts,
        "valve_commands": getattr(world.house, "commands_received", []),
        "final_flow_lpm": world.twin.get("tank.line.flow_lpm"),
        "suspect_assets": [k for k, v in world.twin.snapshot().items()
                           if k.startswith("health.") and v == "suspect"],
        "narration": lines,
    }
    if world.store is not None:
        summary["journal"] = world.store.close()
    if scenario == "energy":
        summary["nilm"] = world.energy.report()
    if not quiet:
        print("--- summary ---")
        for key in ("confirmed", "failed", "final_flow_lpm", "suspect_assets"):
            print(f"{key}: {summary[key]}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the DOMORA closed loop against the virtual house")
    parser.add_argument("--scenario",
                        choices=["leak", "stuck", "energy", "dryrun", "dryrun_stuck",
                                 "comfort", "comfort_blind"],
                        default="leak")
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--journal", metavar="DB", default=None,
                        help="SQLite file to journal twin changes + actions into")
    args = parser.parse_args()
    run(scenario=args.scenario, ticks=args.ticks, journal_db=args.journal)

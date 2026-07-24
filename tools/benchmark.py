"""The week-1 gate: can the hub carry a whole house's load with headroom?

Generates synthetic traffic shaped like the real deployment (N nodes x P
points at R Hz), pushes it through the FULL pipeline — bus -> observer ->
twin -> understander/predictor/planner/verifier -> SQLite journal — as fast
as the machine allows, and reports the headroom multiplier over the
required real-time rate.

Run on the dev PC for a sanity dry-run; the number that matters comes from
running this ON the Arduino UNO Q:

    python -m tools.benchmark --nodes 10 --points 5 --rate 2 --duration 60

Pass/fail guidance (spec §25.3): headroom >= 10x -> comfortable;
3-10x -> acceptable, watch the dashboard's cost; < 3x -> adopt the
LAN-sidecar fallback for AI workloads NOW, not in week 6.
"""

import argparse
import time
import tracemalloc
from pathlib import Path

from hub.agents.actor import Actor
from hub.agents.observer import Observer
from hub.agents.planner import Planner
from hub.agents.predictor import Predictor
from hub.agents.safety import Safety
from hub.agents.understander import Understander
from hub.agents.verifier import Verifier
from hub.core.bus import EventBus
from hub.main import HOUSE_CONFIG
from hub.services.store import Store
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState


def run_benchmark(nodes: int, points: int, rate_hz: float, duration_s: int,
                  db_path: str = "bench_journal.db") -> dict:
    bus = EventBus()
    twin = TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)
    narrate = lambda *a: None  # noqa: E731 — silence agents for clean timing

    Observer(bus, twin, graph, narrate)
    safety = Safety(bus, twin, graph, narrate)
    actor = Actor(bus, twin, graph, narrate)
    ticking = [
        Understander(bus, twin, graph, narrate),
        Predictor(bus, twin, graph, narrate),
        Planner(bus, twin, graph, narrate, safety=safety),
        Verifier(bus, twin, graph, narrate, actor=actor),
    ]

    Path(db_path).unlink(missing_ok=True)
    store = Store(db_path)
    store.attach(bus, twin)

    total_msgs = int(nodes * points * rate_hz * duration_s)
    sim_ticks = duration_s  # one agent tick per simulated second
    msgs_per_tick = max(1, total_msgs // sim_ticks)

    tracemalloc.start()
    t0 = time.perf_counter()
    sent = 0
    for tick in range(sim_ticks):
        twin.now = tick
        for i in range(msgs_per_tick):
            n = i % nodes
            p = i % points
            bus.publish(f"domora/bench{n}/asset{n}/flow_lpm",
                        {"value": (i % 40) * 0.5})
            sent += 1
        for agent in ticking:
            agent.tick(tick)
    elapsed = time.perf_counter() - t0
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    journal = store.close()
    required_rate = nodes * points * rate_hz
    achieved_rate = sent / elapsed if elapsed > 0 else float("inf")

    report = {
        "messages_processed": sent,
        "wall_seconds": round(elapsed, 3),
        "achieved_msgs_per_sec": int(achieved_rate),
        "required_msgs_per_sec": int(required_rate),
        "headroom_x": round(achieved_rate / required_rate, 1),
        "avg_pipeline_latency_us": round(elapsed / sent * 1e6, 1),
        "peak_python_heap_kb": round(peak_bytes / 1e3, 1),
        "journal_rows": journal["points_journal"],
        "journal_db_mb": round(journal["db_bytes"] / 1e6, 2),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nodes", type=int, default=10)
    parser.add_argument("--points", type=int, default=5)
    parser.add_argument("--rate", type=float, default=2.0, help="Hz per point")
    parser.add_argument("--duration", type=int, default=60, help="simulated seconds")
    parser.add_argument("--db", default="bench_journal.db")
    args = parser.parse_args()

    print(f"--- DOMORA hub benchmark: {args.nodes} nodes x {args.points} points "
          f"@ {args.rate} Hz for {args.duration}s (full pipeline + SQLite) ---")
    report = run_benchmark(args.nodes, args.points, args.rate, args.duration, args.db)
    for k, v in report.items():
        print(f"{k:>28}: {v}")
    hx = report["headroom_x"]
    verdict = ("COMFORTABLE (>=10x)" if hx >= 10
               else "ACCEPTABLE (3-10x) — watch dashboard cost" if hx >= 3
               else "INSUFFICIENT (<3x) — adopt LAN-sidecar fallback now")
    print(f"{'verdict':>28}: {verdict}")


if __name__ == "__main__":
    main()

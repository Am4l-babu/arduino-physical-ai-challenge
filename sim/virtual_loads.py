"""Simulated electrical panel: a handful of appliances on a schedule,
summed into one noisy total — exactly what a panel CT clamp sees.

The NILM pipeline gets no ground truth from here; it must recover the
appliances from the aggregate alone. The schedule below produces:
fridge 2 cycles, kettle 1 burst, lamp 1 session, over 120 ticks.
"""

import random

from hub.core.bus import EventBus

BASELINE_W = 80.0  # always-on: router, standby loads

SCHEDULE = [
    # (name, watts, [(t_on, t_off), ...])
    ("fridge", 150.0, [(10, 30), (70, 90)]),
    ("kettle", 1800.0, [(50, 65)]),
    ("lamp", 60.0, [(95, 110)]),
]


class VirtualLoads:
    def __init__(self, bus: EventBus, seed: int = 11) -> None:
        self.bus = bus
        self.rng = random.Random(seed)

    def truth(self, t: int) -> dict:
        """Ground truth for tests only — never published to the bus."""
        return {name: any(a <= t < b for a, b in spans)
                for name, watts, spans in SCHEDULE}

    def tick(self, t: int) -> None:
        watts = BASELINE_W
        for name, load_w, spans in SCHEDULE:
            if any(a <= t < b for a, b in spans):
                watts += load_w
        watts += self.rng.uniform(-1.5, 1.5)
        # docs/BOM_ORDER.md's "FLOW/POWER — panel node" (3x CT + PZEM) is fp1,
        # matching tools/gen_certs.py's default node identities.
        self.bus.publish("domora/fp1/main_panel/power_w", {"value": round(watts, 1)})

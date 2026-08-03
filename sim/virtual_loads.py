"""Simulated electrical panel: a handful of appliances on a schedule,
summed into one noisy total — exactly what a panel CT clamp sees.

The NILM pipeline gets no ground truth from here; it must recover the
appliances from the aggregate alone. The schedule below produces:
fridge 2 cycles, kettle 1 burst, lamp 1 session, over 120 ticks.

By default the published wattage is ideal real power — the case where
nodes/panel_node/panel_node.ino runs with POWER_FROM_PZEM = 1 and the PZEM
on the incomer genuinely measures watts. Pass a `CtChain` to model the other
config, where the node has only current and must assume a power factor; see
that class for why the difference is worth simulating rather than asserting.
"""

import random

from hub.config import nodes
from hub.core.bus import EventBus

BASELINE_W = 80.0  # always-on: router, standby loads
BASELINE_PF = 0.90  # switch-mode supplies — not the resistive 1.0

SCHEDULE = [
    # (name, watts, true power factor, [(t_on, t_off), ...])
    ("fridge", 150.0, 0.62, [(10, 30), (70, 90)]),   # compressor: an induction motor
    ("kettle", 1800.0, 1.00, [(50, 65)]),            # resistive heating element
    ("lamp", 60.0, 0.95, [(95, 110)]),               # LED driver, power-corrected
]


class CtChain:
    """What the panel node's CT-derived power path actually produces.

    A CT clamp measures current and nothing else, so with POWER_FROM_PZEM = 0
    the firmware reports `I x V x ASSUMED_POWER_FACTOR`. It cannot measure the
    power factor it is assuming. Every load whose true PF differs from the
    assumption comes out scaled by `assumed_pf / true_pf` — understated for
    resistive loads, overstated for motors.

    Modeling that here means the consequence for NILM is measured by a test
    rather than claimed in a comment. Defaults mirror
    nodes/panel_node/config.h.example.
    """

    def __init__(self, nominal_v: float = 230.0, assumed_pf: float = 0.95,
                 noise_floor_a: float = 0.05) -> None:
        self.nominal_v = nominal_v
        self.assumed_pf = assumed_pf
        self.noise_floor_a = noise_floor_a

    def derive_watts(self, loads: list) -> float:
        """loads: [(true_watts, true_power_factor), ...] -> what the node reports."""
        amps = sum(w / (self.nominal_v * pf) for w, pf in loads)
        if amps < self.noise_floor_a:
            return 0.0
        return amps * self.nominal_v * self.assumed_pf


class VirtualLoads:
    def __init__(self, bus: EventBus, seed: int = 11, ct_chain: CtChain = None) -> None:
        self.bus = bus
        self.rng = random.Random(seed)
        self.ct_chain = ct_chain

    def truth(self, t: int) -> dict:
        """Ground truth for tests only — never published to the bus."""
        return {name: any(a <= t < b for a, b in spans)
                for name, watts, pf, spans in SCHEDULE}

    def tick(self, t: int) -> None:
        active = [(BASELINE_W, BASELINE_PF)]
        for name, load_w, pf, spans in SCHEDULE:
            if any(a <= t < b for a, b in spans):
                active.append((load_w, pf))

        if self.ct_chain is None:
            watts = sum(w for w, _pf in active)
        else:
            watts = self.ct_chain.derive_watts(active)

        watts += self.rng.uniform(-1.5, 1.5)   # measurement noise, either path
        # The PANEL role (hub/config/nodes.py): docs/BOM_ORDER.md's
        # "FLOW/POWER — panel node", 3x CT + PZEM, nodes/panel_node firmware.
        self.bus.publish(f"domora/{nodes.PANEL_NODE}/main_panel/power_w",
                         {"value": round(watts, 1)})

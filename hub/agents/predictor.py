"""PREDICT — roll the model forward: what happens if nothing changes?

Simple models done well beat deep models done speculatively. A linear
extrapolation of tank level is enough to say "tank empty in ~N minutes",
which is enough for the planner to act early instead of reacting late.
"""

from collections import deque

from hub.agents.base import Agent


class Predictor(Agent):
    name = "predictor"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.history = deque(maxlen=10)
        self._warned = False

    def tick(self, t: int) -> None:
        level = self.twin.get("water_tank.level_pct")
        if level is None:
            return
        self.history.append((t, level))
        if len(self.history) < 5:
            return
        (t0, l0), (t1, l1) = self.history[0], self.history[-1]
        if t1 == t0:
            return
        slope = (l1 - l0) / (t1 - t0)  # pct per tick
        self.twin.set("virtual.tank.slope", round(slope, 3), source="predictor")
        if slope < -0.01:
            eta = int(l1 / -slope)
            self.twin.set("virtual.tank.empty_eta_ticks", eta, source="predictor", confidence=0.6)
            if eta < 2000 and not self._warned:
                self.say(t, f"tank draining at {abs(slope):.2f}%/tick -> empty in ~{eta} ticks")
                self._warned = True

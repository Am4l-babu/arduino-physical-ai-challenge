"""Virtual sensors: state the house never measured, inferred from physics.

The flagship: water balance. If measured flow > 0 while every known fixture
is closed and nobody is home, the state is physically impossible — either a
leak or a lying sensor. Both deserve attention.

Second: pump dry-run protection. A pump drawing running current while the
tank level refuses to rise is either running dry or has a dead impeller —
either way it must be cut before the seals cook.
"""

from collections import deque

from hub.twin.state import TwinState


class WaterBalance:
    """Writes twin point `virtual.water.leak_suspected` with evidence."""

    def __init__(self, persistence_ticks: int = 5) -> None:
        self.persistence = persistence_ticks
        self._breach_streak = 0

    def evaluate(self, twin: TwinState) -> None:
        flow = twin.get("tank.line.flow_lpm", 0.0)
        fixtures_open = twin.get("house.fixtures_open", 0)
        occupied = twin.get("house.occupied", False)

        expected_flow = 0.0 if fixtures_open == 0 else None  # unknown if fixtures open
        breach = expected_flow == 0.0 and flow > 0.3 and not occupied

        self._breach_streak = self._breach_streak + 1 if breach else 0
        suspected = self._breach_streak >= self.persistence

        twin.set(
            "virtual.water.leak_suspected",
            suspected,
            source="virtual/water_balance",
            confidence=min(1.0, self._breach_streak / (self.persistence * 2)) if suspected else 1.0,
        )
        if suspected:
            twin.set(
                "virtual.water.leak_evidence",
                {
                    "flow_lpm": flow,
                    "fixtures_open": fixtures_open,
                    "occupied": occupied,
                    "persisted_ticks": self._breach_streak,
                },
                source="virtual/water_balance",
            )


class PumpProtection:
    """Writes twin point `virtual.pump.dryrun_suspected` with evidence.

    Impossible state: the pump draws running current, yet the tank level is
    not climbing. Current alone can't catch a dry run (a dry pump still pulls
    ~normal amps); it takes the *level slope* to tell lifting water from
    spinning against nothing. Level history is held here across ticks.
    """

    def __init__(self, window: int = 6, rise_threshold: float = 0.2,
                 min_current: float = 1.0, persistence: int = 4) -> None:
        self.window = window                # ticks of level history to slope over
        self.rise_threshold = rise_threshold  # min %/tick a healthy fill shows
        self.min_current = min_current      # amps that count as "pump running"
        self.persistence = persistence
        self._levels = deque(maxlen=window + 1)
        self._streak = 0

    def evaluate(self, twin: TwinState) -> None:
        level = twin.get("water_tank.level_pct")
        current = twin.get("pump.current_a", 0.0)
        state = twin.get("pump.pump_state", "off")

        if level is not None:
            self._levels.append((twin.now, level))

        running = state == "on" and current >= self.min_current
        slope = None
        if len(self._levels) > self.window:
            dt = self._levels[-1][0] - self._levels[0][0]
            dl = self._levels[-1][1] - self._levels[0][1]
            slope = dl / dt if dt else 0.0

        breach = running and slope is not None and slope < self.rise_threshold
        self._streak = self._streak + 1 if breach else 0
        suspected = self._streak >= self.persistence

        twin.set("virtual.pump.dryrun_suspected", suspected,
                 source="virtual/pump_protection",
                 confidence=min(1.0, self._streak / (self.persistence * 2)) if suspected else 1.0)
        if suspected:
            twin.set(
                "virtual.pump.dryrun_evidence",
                {
                    "pump_current_a": current,
                    "level_slope_pct_per_tick": round(slope, 3),
                    "pump_state": state,
                    "persisted_ticks": self._streak,
                },
                source="virtual/pump_protection",
            )

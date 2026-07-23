"""Virtual sensors: state the house never measured, inferred from physics.

The flagship: water balance. If measured flow > 0 while every known fixture
is closed and nobody is home, the state is physically impossible — either a
leak or a lying sensor. Both deserve attention.
"""

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

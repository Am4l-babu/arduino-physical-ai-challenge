"""Virtual sensors: state the house never measured, inferred from physics.

The flagship: water balance. If measured flow > 0 while every known fixture
is closed and nobody is home, the state is physically impossible — either a
leak or a lying sensor. Both deserve attention.

Second: pump dry-run protection. A pump drawing running current while the
tank level refuses to rise is either running dry or has a dead impeller —
either way it must be cut before the seals cook.

Third: AC compressor detection. An IR-commanded appliance answers nothing,
so whether a command landed is itself unmeasured state — recoverable only
from the panel CT, a sensor the appliance has no influence over.
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


class ACRunning:
    """Writes twin point `virtual.comfort.ac_running` with evidence.

    The AC is IR-commanded and answers nothing, so "did the command land?"
    is itself unmeasured state. It is recoverable only from a sensor the
    appliance has no influence over: the panel CT clamp, where a compressor
    start appears as a step of roughly its rated draw that then holds.

    Deliberately a step detector, not a threshold. The panel reading is
    aggregate, so `power > 1000 W` would happily confirm an AC command that
    a kettle satisfied. Comparing against the load level a few ticks back
    asks the narrower question verification actually needs: did the house
    start drawing about a compressor's worth *more* than it just was?

    Edges, not levels, so the point holds between them: once a rising step
    latches it True, only a comparable falling step clears it. A plain
    `latest - min(window)` would read ~0 again as soon as the window filled
    with running samples, un-confirming an AC that is still running.

    Honest limits, both stated rather than designed around:
      - a step detector cannot tell a compressor from any other ~1.2 kW load
        switched on in the same few seconds. hub/twin/nilm.py's signature
        clustering is the real disambiguator; this stays dumb on purpose
        because it gates an actuation and has to be auditable at 2 a.m.
      - spec §8 wants a two-part confirmation: the electrical step *and* a
        temperature slope inflection. Only the fast electrical half gates
        the deadline here — a compressor draws current in seconds, while a
        room bends over minutes, and one expectation carries one deadline.
        The slope is computed and carried in the evidence so the slow half
        is on the record for the journal and for a human to read.
    """

    def __init__(self, window: int = 4, min_step_w: float = 700.0) -> None:
        self.window = window          # ticks of power history to step against
        self.min_step_w = min_step_w  # watts that count as a compressor edge
        self._power = deque(maxlen=window + 1)
        self._temps = deque(maxlen=window + 1)
        self.running = False

    def evaluate(self, twin: TwinState) -> None:
        power = twin.get("main_panel.power_w")
        temp = twin.get("living.temp_c")
        if power is not None:
            self._power.append(power)
        if temp is not None:
            self._temps.append((twin.now, temp))

        step = drop = None
        if len(self._power) > self.window:
            latest = self._power[-1]
            step = latest - min(self._power)
            drop = max(self._power) - latest
            if not self.running and step >= self.min_step_w:
                self.running = True
            elif self.running and drop >= self.min_step_w:
                self.running = False

        twin.set("virtual.comfort.ac_running", self.running,
                 source="virtual/ac_running", confidence=0.8)
        if self.running:
            twin.set(
                "virtual.comfort.ac_evidence",
                {
                    "power_w": self._power[-1] if self._power else None,
                    "step_w": round(step, 1) if step is not None else None,
                    "temp_slope_c_per_tick": self._temp_slope(),
                    "detector": "panel CT step (independent of the IR command)",
                },
                source="virtual/ac_running",
            )

    def _temp_slope(self):
        """Supporting evidence, not a gate — see the class docstring."""
        if len(self._temps) < 2:
            return None
        dt = self._temps[-1][0] - self._temps[0][0]
        if not dt:
            return None
        return round((self._temps[-1][1] - self._temps[0][1]) / dt, 3)

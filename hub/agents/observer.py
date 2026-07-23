"""OBSERVE — ingest and validate before believing.

Subscribes to every sensor topic, range-checks readings, and writes valid
values into the twin. Rejected readings are quarantined loudly, never
dropped silently: a sensor that lies is itself a finding.
"""

from hub.agents.base import Agent

RANGES = {
    "flow_lpm": (0.0, 60.0),
    "power_w": (0.0, 25000.0),
    "current_a": (0.0, 30.0),
    "level_pct": (0.0, 100.0),
    "radar": (0, 1),
    "pir": (0, 1),
    "fixtures_open": (0, 20),
    "valve_state": None,  # enum, checked separately
    "pump_state": None,   # enum
}


class Observer(Agent):
    name = "observer"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rejected = 0
        self.bus.subscribe("domora/+/+/+", self._on_reading)

    def _on_reading(self, topic: str, payload: dict) -> None:
        parts = topic.split("/")
        if parts[1] in ("cmd", "plan", "verify", "alert"):
            return
        _, node, asset, point = parts
        value = payload.get("value")
        bounds = RANGES.get(point)
        if bounds is not None and isinstance(value, (int, float)):
            lo, hi = bounds
            if not (lo <= value <= hi):
                self.rejected += 1
                self.say(self.twin.now, f"QUARANTINED {topic}={value} (out of range {lo}-{hi})")
                self.twin.set(f"health.{node}.{point}", "suspect", source="observer")
                return
        self.twin.set(f"{asset}.{point}" if asset != node else point, value, source=node)

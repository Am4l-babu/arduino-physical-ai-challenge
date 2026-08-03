"""A fake house that publishes real-shaped sensor data onto the bus.

Physics, minimally: a hidden leak opens on the main line at LEAK_AT;
line flow jumps while every fixture is closed and nobody is home; the
tank drains slowly while the leak runs. The valve actuator listens on
its command topic — and can be configured to be stuck, so the failure
path of verification can be exercised as easily as the happy path.
"""

import random

from hub.config import nodes
from hub.core.bus import EventBus

LEAK_AT = 30
LEAK_FLOW_LPM = 2.0


class VirtualHouse:
    def __init__(self, bus: EventBus, stuck_valve: bool = False, seed: int = 7) -> None:
        self.bus = bus
        self.stuck_valve = stuck_valve
        self.rng = random.Random(seed)
        self.valve_open = True
        self.leak_active = False
        self.tank_level = 62.0
        self.commands_received = []
        bus.subscribe("domora/cmd/main_valve/+", self._on_valve_cmd)

    def _on_valve_cmd(self, topic: str, payload: dict) -> None:
        command = topic.split("/")[3]
        self.commands_received.append(command)
        if self.stuck_valve:
            return  # actuator accepts the command and silently does nothing
        if command == "close":
            self.valve_open = False
        elif command == "open":
            self.valve_open = True

    def tick(self, t: int) -> None:
        if t == LEAK_AT:
            self.leak_active = True

        flow = 0.0
        if self.leak_active and self.valve_open:
            flow = LEAK_FLOW_LPM + self.rng.uniform(-0.1, 0.1)
            self.tank_level = max(0.0, self.tank_level - 0.05)

        noise = self.rng.uniform(-0.15, 0.15)
        # Identities come from hub/config/nodes.py — the one place the
        # board-to-role assumption lives. Flow + valve are the VALVE role,
        # level is the TANK role; today those are the same board (fp2), and
        # if the rig ever splits them, repointing TANK_NODE there moves the
        # level topic without touching this file. Read via module attribute
        # at publish time, never from-imported, so a repoint propagates.
        self.bus.publish(f"domora/{nodes.VALVE_NODE}/tank.line/flow_lpm",
                         {"value": round(max(0.0, flow), 2)})
        self.bus.publish(f"domora/{nodes.TANK_NODE}/water_tank/level_pct",
                         {"value": round(self.tank_level + noise, 2)})
        self.bus.publish(f"domora/{nodes.VALVE_NODE}/main_valve/valve_state",
                         {"value": "open" if self.valve_open else "closed"})
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living/radar", {"value": 0})
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living/pir", {"value": 0})
        self.bus.publish(f"domora/{nodes.ENV_NODE}/house/fixtures_open", {"value": 0})

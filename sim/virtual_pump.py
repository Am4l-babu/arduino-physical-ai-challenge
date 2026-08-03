"""A fake tank+pump that can run dry, for the second closed loop.

Physics, minimally (spec §7.2, line 324): the pump lifts water into the
roof tank. A healthy pump ON shows normal current AND a rising level. When
suction is lost (well/sump runs dry, impaired impeller), the pump keeps
drawing ~normal current but the level stops rising — the signature of a
**dry run**, which cooks the seals in minutes. The protection loop must cut
the pump and verify, through an *independent* sensor (the CT clamp), that it
actually stopped — never trusting the relay's own ACK.

Like VirtualHouse, the relay can be configured stuck, so verification's
failure path is exercised as easily as its success path.
"""

import random

from hub.config import nodes
from hub.core.bus import EventBus

DRY_AT = 25            # tick the suction is lost
RUN_CURRENT = 4.5      # nominal running current (A)
FILL_RATE = 0.8        # %/tick the level rises while pumping healthy


class VirtualPump:
    def __init__(self, bus: EventBus, stuck_relay: bool = False, seed: int = 11) -> None:
        self.bus = bus
        self.stuck_relay = stuck_relay
        self.rng = random.Random(seed)
        self.pump_on = True
        self.level = 20.0      # tank starts low; the pump is filling it
        self.dry = False
        self.current = RUN_CURRENT
        self.commands_received = []
        bus.subscribe("domora/cmd/pump/+", self._on_pump_cmd)

    def _on_pump_cmd(self, topic: str, payload: dict) -> None:
        command = topic.split("/")[3]
        self.commands_received.append(command)
        if self.stuck_relay:
            return  # welded relay: accepts the command, keeps running
        if command == "off":
            self.pump_on = False
        elif command == "on":
            self.pump_on = True

    def tick(self, t: int) -> None:
        if t == DRY_AT:
            self.dry = True

        if self.pump_on:
            # A dry-running pump still draws ~normal (even slightly higher)
            # current — that's exactly why current alone can't catch it.
            self.current = RUN_CURRENT + (0.4 if self.dry else 0.0) + self.rng.uniform(-0.1, 0.1)
            if not self.dry:
                self.level = min(100.0, self.level + FILL_RATE)
            # dry: no water moved, so the level does not rise
        else:
            self.current = self.rng.uniform(0.0, 0.05)

        noise = self.rng.uniform(-0.05, 0.05)
        # All three points are the TANK role (hub/config/nodes.py) — level,
        # pump CT, and pump state live on whichever board serves the tank.
        # Module-attribute access at publish time so repointing TANK_NODE
        # propagates without touching this file.
        self.bus.publish(f"domora/{nodes.TANK_NODE}/pump/current_a",
                         {"value": round(max(0.0, self.current), 2)})
        self.bus.publish(f"domora/{nodes.TANK_NODE}/pump/pump_state",
                         {"value": "on" if self.pump_on else "off"})
        self.bus.publish(f"domora/{nodes.TANK_NODE}/water_tank/level_pct",
                         {"value": round(self.level + noise, 2)})

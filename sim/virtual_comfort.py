"""A dumb, IR-controlled air conditioner — the first actuator with no
feedback path at all.

Every actuator DOMORA commands today is one it can also sense: the main
valve has a position report, the pump relay has a CT clamp on its own
circuit. An AC driven by a captured IR remote code has neither. It is
another brand's appliance, on no network, with no API, and the only thing
leaving the hub is an infrared pulse train fired across the room. Nothing
comes back. There is no ACK to trust even if we wanted to trust one.

That makes it the sharpest available test of the expectation contract: the
only way to learn whether the command landed is to catch the compressor
starting on a *completely different* sensor — the panel CT clamp — and to
watch the room temperature bend. Spec §8 (zone node) names this exact
verification: "commanded AC on -> expect supply-side current signature at
panel within 60 s AND temp slope inflection within 10 min".

Physics, minimally: the room is a first-order RC model drifting toward the
outdoor temperature; a running compressor pulls it toward the unit's own
floor and adds its rated draw to the panel aggregate. Compressors do not
start the instant they are told to (`COMPRESSOR_LAG_TICKS`), which is why
the expectation carries a deadline rather than checking the very next tick.

Fault injection `ir_blind=True`: the appliance never receives the signal —
blaster misaimed, LED dead, or a box left in front of it. The failure is
*silent*. The hub transmits happily and nothing hears. That is precisely
the failure mode an ACK-trusting system cannot see, and the reason
`living_ac.ir_last_cmd` below is published as what was *transmitted*,
never as what the appliance is doing.
"""

import random

from hub.config import nodes
from hub.core.bus import EventBus

OUTDOOR_C = 34.0            # a hot afternoon; the room drifts toward this
START_C = 27.0
AC_FLOOR_C = 20.0           # what the unit drives toward while running
TAU_HEAT_TICKS = 60.0       # room time constant, AC off
TAU_COOL_TICKS = 25.0       # room time constant, AC running
COMPRESSOR_W = 1200.0       # rated draw of the compressor once spinning
BASE_LOAD_W = 180.0         # fridge, router, standby — the aggregate floor
COMPRESSOR_LAG_TICKS = 2    # IR received -> compressor actually drawing


class VirtualComfort:
    def __init__(self, bus: EventBus, ir_blind: bool = False, seed: int = 13) -> None:
        self.bus = bus
        self.ir_blind = ir_blind
        self.rng = random.Random(seed)
        self.temp_c = START_C

        # Three separate pieces of state, deliberately not collapsed:
        #   ir_last_cmd  — what the blaster transmitted (all the node knows)
        #   ac_accepted  — whether the appliance actually heard it
        #   ac_running   — whether the compressor is actually drawing power
        # A system that trusts its own command confuses the first for the
        # third. Keeping them apart is what lets `ir_blind` be modelled at all.
        self.ir_last_cmd = "off"
        self.ac_accepted = False
        self.ac_running = False

        self._lag = 0
        self.commands_received = []
        bus.subscribe("domora/cmd/living_ac/+", self._on_ac_cmd)

    def _on_ac_cmd(self, topic: str, payload: dict) -> None:
        command = topic.split("/")[3]
        self.commands_received.append(command)
        # The blaster fires regardless — it has no way to know if anything
        # is listening. This assignment is the shadow state, not the truth.
        self.ir_last_cmd = command

        if self.ir_blind:
            return  # pulse train goes into the void; appliance never hears it

        if command == "on":
            if not self.ac_accepted:
                self.ac_accepted = True
                self._lag = COMPRESSOR_LAG_TICKS
        elif command == "off":
            self.ac_accepted = False
            self._lag = 0

    def tick(self, t: int) -> None:
        if self.ac_accepted:
            if self._lag > 0:
                self._lag -= 1      # compressor spinning up, drawing nothing yet
            else:
                self.ac_running = True
        else:
            self.ac_running = False

        target = AC_FLOOR_C if self.ac_running else OUTDOOR_C
        tau = TAU_COOL_TICKS if self.ac_running else TAU_HEAT_TICKS
        self.temp_c += (target - self.temp_c) / tau

        watts = BASE_LOAD_W + (COMPRESSOR_W if self.ac_running else 0.0)
        watts += self.rng.uniform(-4.0, 4.0)

        # The PANEL role: the independent witness. Nothing about this reading
        # comes from the AC or from the node that commanded it.
        self.bus.publish(f"domora/{nodes.PANEL_NODE}/main_panel/power_w",
                         {"value": round(watts, 1)})

        # The ENV role: the living-room node — BME280 for temperature, radar
        # for presence, and the IR blaster bolted to the same board (spec §8;
        # no new node identity, the blaster is an LED on hardware already in
        # the BOM).
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living/temp_c",
                         {"value": round(self.temp_c + self.rng.uniform(-0.05, 0.05), 2)})
        # Someone is home and sitting still — the OCCUPIED_STILL case radar
        # exists to catch, and the only justification for cooling at all.
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living/radar", {"value": 1})
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living/pir", {"value": 0})
        self.bus.publish(f"domora/{nodes.ENV_NODE}/living_ac/ir_last_cmd",
                         {"value": self.ir_last_cmd})

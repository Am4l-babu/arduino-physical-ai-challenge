"""THINK — turn readings into meaning.

Fuses raw points into semantic state (occupancy, water balance) and writes
the conclusions back into the twin with confidence attached. This is state
estimation: the least glamorous and most valuable stage of the loop.
"""

from hub.agents.base import Agent
from hub.twin.virtual_sensors import PumpProtection, WaterBalance


class Understander(Agent):
    name = "understander"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.water_balance = WaterBalance()
        self.pump_protection = PumpProtection()
        self._announced_leak = False
        self._announced_dryrun = False

    def tick(self, t: int) -> None:
        radar = self.twin.get("living.radar", 0)
        pir = self.twin.get("living.pir", 0)
        # Radar catches still humans; PIR confirms motion. Either one is
        # enough to call the house occupied — absence needs both silent.
        occupied = bool(radar or pir)
        self.twin.set("house.occupied", occupied, source="understander",
                      confidence=0.95 if radar else 0.7)

        self.water_balance.evaluate(self.twin)
        self.pump_protection.evaluate(self.twin)

        if self.twin.get("virtual.water.leak_suspected") and not self._announced_leak:
            ev = self.twin.get("virtual.water.leak_evidence", {})
            self.say(t, f"impossible state: flow={ev.get('flow_lpm')} L/min with "
                        f"{ev.get('fixtures_open')} fixtures open and house empty "
                        f"({ev.get('persisted_ticks')} ticks persistent) -> leak suspected")
            self._announced_leak = True

        if self.twin.get("virtual.pump.dryrun_suspected") and not self._announced_dryrun:
            ev = self.twin.get("virtual.pump.dryrun_evidence", {})
            self.say(t, f"impossible state: pump drawing {ev.get('pump_current_a')} A but "
                        f"tank rising {ev.get('level_slope_pct_per_tick')} %/tick "
                        f"({ev.get('persisted_ticks')} ticks persistent) -> dry run suspected")
            self._announced_dryrun = True

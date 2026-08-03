"""PLAN — decide what to do, and state what success will look like first.

The planner never emits a bare command. Every action carries:
  - cause: why (traceable to twin state)
  - evidence: the readings that justify it
  - expectation: a falsifiable claim with a deadline

That expectation contract is what makes verification possible, and
verification is what separates a twin from a shadow.
"""

from hub.agents.base import Action, Agent, Expectation
from hub.agents.safety import Safety

COMFORT_MAX_C = 29.0   # above this, an occupied room is worth cooling


class Planner(Agent):
    name = "planner"

    def __init__(self, *args, safety: Safety, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.safety = safety
        self._open_causes = set()  # causes already being handled

    def tick(self, t: int) -> None:
        self._rule_leak_response(t)
        self._rule_dryrun_response(t)
        self._rule_comfort_response(t)

    def _rule_leak_response(self, t: int) -> None:
        if not self.twin.get("virtual.water.leak_suspected"):
            return
        cause = "leak:main_line"
        if cause in self._open_causes:
            return

        shutoff = self.graph.upstream_shutoff("main_line")
        if shutoff is None:
            self.say(t, "leak suspected but no upstream shutoff exists — escalating")
            self.bus.publish("domora/alert/critical", {"cause": cause, "reason": "no shutoff"})
            self._open_causes.add(cause)
            return

        action = Action(
            command_topic=f"domora/cmd/{shutoff}/close",
            payload={},
            cause=cause,
            evidence=self.twin.get("virtual.water.leak_evidence", {}),
            expectation=Expectation(
                point="tank.line.flow_lpm",
                predicate=lambda v: isinstance(v, (int, float)) and v < 0.1,
                describe="line flow falls below 0.1 L/min",
                deadline_ticks=10,
            ),
        )
        self.say(t, f"plan: close {shutoff} (upstream of leak) — "
                    f"expect {action.expectation.describe} within {action.expectation.deadline_ticks} ticks")
        if self.safety.check(action):
            self._open_causes.add(cause)
            self.bus.publish("domora/plan/action", {"action": action})

    def _rule_dryrun_response(self, t: int) -> None:
        if not self.twin.get("virtual.pump.dryrun_suspected"):
            return
        cause = "dryrun:pump"
        if cause in self._open_causes:
            return

        action = Action(
            command_topic="domora/cmd/pump/off",
            payload={},
            cause=cause,
            evidence=self.twin.get("virtual.pump.dryrun_evidence", {}),
            expectation=Expectation(
                # Verified through the CT clamp, independent of the relay's ACK:
                # a stopped pump draws no current.
                point="pump.current_a",
                predicate=lambda v: isinstance(v, (int, float)) and v < 0.2,
                describe="pump current falls to ~0 (pump stopped)",
                deadline_ticks=8,
            ),
        )
        self.say(t, f"plan: cut pump (running dry) — "
                    f"expect {action.expectation.describe} within {action.expectation.deadline_ticks} ticks")
        if self.safety.check(action):
            self._open_causes.add(cause)
            self.bus.publish("domora/plan/action", {"action": action})

    def _rule_comfort_response(self, t: int) -> None:
        """Cool an occupied room that has drifted too warm.

        Unlike the leak and dry-run rules, this one is not a response to an
        impossible state — nothing is broken, the house is just hot. What
        makes it worth having in this codebase is the actuator: the AC is
        another brand's appliance driven by a captured IR code, with no
        network, no API and no return path. There is no ACK to trust, so
        the expectation carries the entire weight of knowing whether the
        command landed — verified on the panel CT, which the appliance has
        no way to influence (sim/virtual_comfort.py explains the physics).
        """
        temp = self.twin.get("living.temp_c")
        if not isinstance(temp, (int, float)) or temp <= COMFORT_MAX_C:
            return
        if not self.twin.get("house.occupied"):
            return          # safety would veto anyway; don't propose waste
        cause = "comfort:living_hot"
        if cause in self._open_causes:
            return

        action = Action(
            command_topic="domora/cmd/living_ac/on",
            payload={},
            cause=cause,
            evidence={"living_temp_c": temp, "comfort_max_c": COMFORT_MAX_C,
                      "occupied": True},
            expectation=Expectation(
                # Verified through the panel CT, independent of the IR
                # blaster: a compressor that actually started shows up as a
                # step change in whole-house draw. If the blaster is
                # misaimed or its LED is dead, nothing appears here and the
                # loop fails loudly instead of assuming success.
                point="virtual.comfort.ac_running",
                predicate=lambda v: v is True,
                describe="compressor draw appears at the panel (AC really started)",
                deadline_ticks=8,
            ),
        )
        self.say(t, f"plan: IR 'on' to living_ac ({temp} C, occupied) — "
                    f"expect {action.expectation.describe} within {action.expectation.deadline_ticks} ticks")
        if self.safety.check(action):
            self._open_causes.add(cause)
            self.bus.publish("domora/plan/action", {"action": action})

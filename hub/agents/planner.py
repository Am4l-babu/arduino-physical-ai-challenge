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


class Planner(Agent):
    name = "planner"

    def __init__(self, *args, safety: Safety, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.safety = safety
        self._open_causes = set()  # causes already being handled

    def tick(self, t: int) -> None:
        self._rule_leak_response(t)
        self._rule_dryrun_response(t)

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

"""VERIFY — never trust an ACK; trust independent physical evidence.

Every dispatched action is held open until its expectation is either
confirmed by the twin (via a *different* sensor than the actuator's own
feedback) or its deadline passes. Failure path: retry once, then escalate
and mark the asset suspect. A stuck valve is discovered the day it sticks,
not the day of the flood.
"""

from typing import List

from hub.agents.actor import Actor
from hub.agents.base import Action, Agent


class Verifier(Agent):
    name = "verifier"

    def __init__(self, *args, actor: Actor, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.pending: List[Action] = []
        self.confirmed: List[Action] = []
        self.failed: List[Action] = []
        self.bus.subscribe("domora/act/dispatched", self._on_dispatched)

    def _on_dispatched(self, topic: str, payload: dict) -> None:
        action = payload["action"]
        if action not in self.pending:
            self.pending.append(action)

    def tick(self, t: int) -> None:
        for action in list(self.pending):
            exp = action.expectation
            value = self.twin.get(exp.point)
            if exp.predicate(value):
                action.status = "confirmed"
                self.pending.remove(action)
                self.confirmed.append(action)
                self.say(t, f"VERIFIED action#{action.id}: {exp.describe} "
                            f"(observed {exp.point}={value}) — loop closed")
                self.bus.publish("domora/verify/confirmed", {"action_id": action.id})
            elif t - action.dispatched_at > exp.deadline_ticks:
                if action.retries < 1:
                    self.say(t, f"expectation NOT met for action#{action.id} "
                                f"({exp.point}={value}) — retrying once")
                    self.actor.redispatch(action)
                else:
                    action.status = "failed"
                    self.pending.remove(action)
                    self.failed.append(action)
                    asset = action.command_topic.split("/")[2]
                    self.twin.set(f"health.{asset}", "suspect", source="verifier")
                    self.say(t, f"VERIFICATION FAILED action#{action.id}: {exp.point}={value} "
                                f"after retry — {asset} marked suspect, ESCALATING to human")
                    self.bus.publish("domora/alert/critical", {
                        "action_id": action.id,
                        "cause": action.cause,
                        "asset": asset,
                        "reason": f"actuation unverified: expected {exp.describe}, observed {value}",
                    })

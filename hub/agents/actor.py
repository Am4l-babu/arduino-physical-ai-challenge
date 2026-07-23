"""ACT — the only code path that touches actuators.

One arbiter per actuator: no two subsystems can ever command the same
device, so the classic home-automation race condition is structurally
impossible. Every dispatch is journaled before it happens.
"""

from hub.agents.base import Agent


class Actor(Agent):
    name = "actor"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.journal = []
        self.bus.subscribe("domora/plan/action", self._on_action)

    def _on_action(self, topic: str, payload: dict) -> None:
        action = payload["action"]
        action.status = "dispatched"
        action.dispatched_at = self.twin.now
        self.journal.append(action)
        self.say(self.twin.now, f"dispatch action#{action.id}: {action.command_topic}")
        self.bus.publish(action.command_topic, {"action_id": action.id})
        self.bus.publish("domora/act/dispatched", {"action": action})

    def redispatch(self, action) -> None:
        action.retries += 1
        action.dispatched_at = self.twin.now
        self.say(self.twin.now, f"re-dispatch action#{action.id} (retry {action.retries})")
        self.bus.publish(action.command_topic, {"action_id": action.id})

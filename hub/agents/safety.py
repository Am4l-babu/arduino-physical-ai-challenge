"""SAFETY — the plane with veto power over everything above it.

Two mechanisms, both deliberately dumb:
1. A capability table: what the autonomous planner may EVER command.
   Anything not listed is unrepresentable, not merely rejected.
2. Invariants checked against every proposed action.

No ML in this file, by design. Safety logic must be auditable at 2 a.m.
"""

from hub.agents.base import Action, Agent

# The planner may close/stop things on its own authority. It may never
# open a gas line, unlock anything, or energize a heat-producing load.
AUTONOMOUS_CAPABILITIES = {
    ("main_valve", "close"),
    ("main_valve", "open"),   # open allowed only via invariant below
    ("pump", "off"),
}


class Safety(Agent):
    name = "safety"

    def check(self, action: Action) -> bool:
        asset = action.command_topic.split("/")[2]
        command = action.command_topic.split("/")[3]

        if (asset, command) not in AUTONOMOUS_CAPABILITIES:
            self._veto(action, f"{asset}:{command} is outside autonomous capabilities")
            return False

        # Invariant: never reopen the main valve while a leak is suspected.
        if command == "open" and self.twin.get("virtual.water.leak_suspected"):
            self._veto(action, "cannot reopen water while leak suspected")
            return False

        return True

    def _veto(self, action: Action, reason: str) -> None:
        action.status = "vetoed"
        self.say(self.twin.now, f"VETO action#{action.id}: {reason}")
        self.bus.publish("domora/alert/veto", {"action_id": action.id, "reason": reason})

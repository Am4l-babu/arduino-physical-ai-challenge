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
    ("living_ac", "on"),      # first energizing capability — see review below
    ("living_ac", "off"),
}

# --- Invariant review: adding ("living_ac", "on") -----------------------
#
# What changed. Every prior entry either stops or closes something; a
# failure to act is the risk, and acting is the safe direction. `living_ac:on`
# is the first capability that *energizes* a load on the planner's own
# authority, so for the first time a false positive causes action rather
# than inaction. That is the widening under review.
#
# Why it is admissible. The load is a cooling appliance on its own breaker,
# switched by an infrared code — DOMORA never carries its current and cannot
# defeat its overload protection. The worst outcome of a stuck-on AC is a
# cold room and a power bill, which is a cost, not a hazard. Contrast the
# entries this table still refuses: gas, locks, and heaters can injure.
#
# The bounding invariant (enforced below): never energize the AC in an empty
# house. Three reasons, in order of weight:
#   1. The only justification for this action is that a person is
#      uncomfortable. No person, no justification — so the invariant is not
#      a bolt-on guard, it is the action's own precondition made checkable.
#   2. It bounds the blast radius of a lying thermometer. A stuck-high
#      temperature sensor can at worst cool a room someone is sitting in;
#      it cannot run a compressor for a week in an empty house.
#   3. `house.occupied` is fused from radar + PIR by the understander, so
#      the guard reads an independently-derived point rather than the same
#      sensor that triggered the action.
#
# What this invariant does NOT cover, stated rather than papered over. The
# table admits `on`/`off`, not a mode. Whether "on" means cool or heat is a
# property of which IR code was captured during provisioning, not of
# anything checkable here — a reversible heat pump learned from its HEAT
# button would energize a heat-producing load while satisfying every check
# in this file. Enforcement lives in the provisioning step (capture the COOL
# code), and until that step verifies the mode, this capability is only as
# safe as the code that was learned. Named here so the gap is on the record.
# ------------------------------------------------------------------------


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

        # Invariant: never energize the AC in an empty house (see review above).
        if asset == "living_ac" and command == "on" and not self.twin.get("house.occupied"):
            self._veto(action, "cannot run the AC with nobody home")
            return False

        return True

    def _veto(self, action: Action, reason: str) -> None:
        action.status = "vetoed"
        self.say(self.twin.now, f"VETO action#{action.id}: {reason}")
        self.bus.publish("domora/alert/veto", {"action_id": action.id, "reason": reason})

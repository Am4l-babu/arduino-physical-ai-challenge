"""Third closed loop: an IR-commanded AC that cannot acknowledge anything.

The leak and dry-run loops both verify an actuator the hub can also sense
directly. This one verifies an appliance of another brand, on no network,
reachable only by an infrared code fired across the room — nothing comes
back, ever. Same expectation contract: success path (compressor start seen
on the panel CT, a sensor the appliance cannot influence) and failure path
(blaster misaimed / LED dead: the code goes into the void, verification
fails, escalate, mark the unit suspect).
"""

from hub.agents.base import Action, Expectation
from hub.agents.safety import Safety
from hub.core.bus import EventBus
from hub.main import HOUSE_CONFIG, run, step, wire
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState
from hub.twin.virtual_sensors import ACRunning


def _ac_on_action() -> Action:
    return Action(
        command_topic="domora/cmd/living_ac/on",
        payload={}, cause="comfort:living_hot", evidence={},
        expectation=Expectation(point="virtual.comfort.ac_running",
                                predicate=lambda v: v is True,
                                describe="compressor draw appears", deadline_ticks=8),
    )


def test_ac_command_is_verified_via_panel_ct():
    s = run(scenario="comfort", quiet=True)
    assert len(s["confirmed"]) == 1, "the AC start should be verified at the panel"
    assert s["failed"] == []
    assert s["valve_commands"] == ["on"], "one IR command, no retry needed"
    assert s["suspect_assets"] == []


def test_ir_blind_ac_fails_verification_and_escalates():
    s = run(scenario="comfort_blind", quiet=True)
    assert s["confirmed"] == []
    assert len(s["failed"]) == 1, "a blind blaster must fail verification after retry"
    assert s["valve_commands"].count("on") == 2, "exactly one retry"
    assert "health.living_ac" in s["suspect_assets"]
    critical = [a for a in s["alerts"] if a["topic"] == "domora/alert/critical"]
    assert critical, "failure must escalate to a critical alert"
    assert "unverified" in critical[0]["reason"]


def test_blind_ac_shadow_state_would_have_fooled_an_ack_trusting_system():
    """The reason this loop exists at all.

    With the blaster blind, the only thing the node can report is what it
    transmitted — and that says "on". A system that treated its own command
    as state would show a cooling AC, a satisfied user, and no fault. The
    panel CT says otherwise, and the panel CT is what the loop believes.
    """
    world = wire("comfort_blind", lambda *a: None)
    for t in range(60):
        step(world, t)

    # What the house actually did: nothing. The appliance never heard a thing.
    assert world.house.ac_running is False
    assert world.house.ac_accepted is False

    # What a command-trusting system would have believed.
    assert world.twin.get("living_ac.ir_last_cmd") == "on"

    # What the independent sensor concluded, and what the loop acted on.
    assert world.twin.get("virtual.comfort.ac_running") is False
    assert len(world.verifier.failed) == 1
    assert world.twin.get("health.living_ac") == "suspect"


def test_safety_vetoes_running_the_ac_in_an_empty_house():
    """The invariant added alongside the ("living_ac", "on") capability."""
    twin = TwinState()
    safety = Safety(EventBus(), twin, KnowledgeGraph.load(HOUSE_CONFIG), lambda *a: None)

    twin.set("house.occupied", False, source="test")
    empty_house = _ac_on_action()
    assert safety.check(empty_house) is False
    assert empty_house.status == "vetoed"

    twin.set("house.occupied", True, source="test")
    assert safety.check(_ac_on_action()) is True, "occupied is the whole justification"


def test_safety_still_refuses_capabilities_outside_the_table():
    """Widening the table for living_ac must not widen it for anything else."""
    twin = TwinState()
    twin.set("house.occupied", True, source="test")
    safety = Safety(EventBus(), twin, KnowledgeGraph.load(HOUSE_CONFIG), lambda *a: None)

    for topic in ("domora/cmd/geyser/on", "domora/cmd/front_door/unlock",
                  "domora/cmd/living_ac/heat"):
        action = _ac_on_action()
        action.command_topic = topic
        assert safety.check(action) is False, f"{topic} must stay unrepresentable"


def test_ac_detector_needs_a_real_step_not_a_high_reading():
    """No false confirmation from jitter or a slow ramp.

    A fixed threshold would confirm on any large load; a step detector must
    see the house start drawing ~a compressor more than it just was.
    """
    twin = TwinState()
    detector = ACRunning()
    watts = 180.0
    for t in range(40):
        twin.now = t
        watts += 50.0 if t > 10 else 0.0   # slow ramp: big total, tiny per-window step
        twin.set("main_panel.power_w", watts + (t % 3), source="test")
        twin.set("living.temp_c", 30.0, source="test")
        detector.evaluate(twin)
        assert twin.get("virtual.comfort.ac_running") is False, f"false trip at t={t}"


def test_ac_detector_latches_on_and_releases_on_the_falling_edge():
    """The point must hold while the compressor runs, then clear when it stops."""
    twin = TwinState()
    detector = ACRunning()

    def feed(t, watts):
        twin.now = t
        twin.set("main_panel.power_w", watts, source="test")
        twin.set("living.temp_c", 26.0, source="test")
        detector.evaluate(twin)

    for t in range(6):
        feed(t, 180.0)
    assert twin.get("virtual.comfort.ac_running") is False

    feed(6, 1380.0)                       # compressor starts
    assert twin.get("virtual.comfort.ac_running") is True
    for t in range(7, 20):                # ...and keeps running well past the window
        feed(t, 1380.0)
        assert twin.get("virtual.comfort.ac_running") is True, f"un-latched at t={t}"

    feed(20, 180.0)                       # compressor stops
    assert twin.get("virtual.comfort.ac_running") is False


if __name__ == "__main__":
    test_ac_command_is_verified_via_panel_ct()
    test_ir_blind_ac_fails_verification_and_escalates()
    test_blind_ac_shadow_state_would_have_fooled_an_ack_trusting_system()
    test_safety_vetoes_running_the_ac_in_an_empty_house()
    test_safety_still_refuses_capabilities_outside_the_table()
    test_ac_detector_needs_a_real_step_not_a_high_reading()
    test_ac_detector_latches_on_and_releases_on_the_falling_edge()
    print("all 7 comfort tests passed")

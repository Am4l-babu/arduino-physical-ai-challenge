"""Second closed loop: pump dry-run protection (spec §25.6).

Same expectation-contract discipline as the leak loop — success path (cut
verified through the CT clamp, independent of the relay ACK) and failure path
(welded relay: verification fails, escalate, mark the pump suspect).
"""

from hub.main import run


def test_dryrun_is_detected_cut_and_verified():
    s = run(scenario="dryrun", quiet=True)
    assert len(s["confirmed"]) == 1, "the pump cut should be verified"
    assert s["failed"] == []
    assert "off" in s["valve_commands"], "the pump must have been commanded off"
    assert s["suspect_assets"] == []


def test_stuck_relay_fails_verification_and_escalates():
    s = run(scenario="dryrun_stuck", quiet=True)
    assert s["confirmed"] == []
    assert len(s["failed"]) == 1, "a welded relay must fail verification after retry"
    assert s["valve_commands"].count("off") == 2, "exactly one retry"
    assert "health.pump" in s["suspect_assets"]
    critical = [a for a in s["alerts"] if a["topic"] == "domora/alert/critical"]
    assert critical, "failure must escalate to a critical alert"
    assert "unverified" in critical[0]["reason"]


def test_dryrun_detection_needs_both_current_and_flat_level():
    """A healthy pump (current normal AND level rising) must never trip the cut."""
    from collections import deque
    from hub.twin.state import TwinState
    from hub.twin.virtual_sensors import PumpProtection

    twin = TwinState()
    prot = PumpProtection()
    level = 20.0
    for t in range(40):
        twin.now = t
        twin.set("pump.pump_state", "on", source="test")
        twin.set("pump.current_a", 4.5, source="test")
        level += 0.8                       # healthy fill: level climbs every tick
        twin.set("water_tank.level_pct", level, source="test")
        prot.evaluate(twin)
        assert twin.get("virtual.pump.dryrun_suspected") is False


if __name__ == "__main__":
    test_dryrun_is_detected_cut_and_verified()
    test_stuck_relay_fails_verification_and_escalates()
    test_dryrun_detection_needs_both_current_and_flat_level()
    print("all 3 dry-run tests passed")

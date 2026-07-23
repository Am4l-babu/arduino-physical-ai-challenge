"""Closed-loop regression tests: the two scenarios every demo depends on.

Run with:  python -m pytest tests/ -q     (or: python -m tests.test_loop)
"""

from hub.main import run


def test_leak_is_detected_closed_and_verified():
    s = run(scenario="leak", quiet=True)
    assert len(s["confirmed"]) == 1, "leak action should be verified"
    assert s["failed"] == []
    assert "close" in s["valve_commands"]
    assert s["final_flow_lpm"] == 0.0
    assert s["suspect_assets"] == []


def test_stuck_valve_fails_verification_and_escalates():
    s = run(scenario="stuck", quiet=True)
    assert s["confirmed"] == []
    assert len(s["failed"]) == 1, "stuck valve must fail verification after retry"
    assert s["valve_commands"].count("close") == 2, "exactly one retry"
    assert "health.main_valve" in s["suspect_assets"]
    critical = [a for a in s["alerts"] if a["topic"] == "domora/alert/critical"]
    assert critical, "failure must escalate to a critical alert"
    assert s["final_flow_lpm"] > 1.0, "water is still flowing — which is exactly the point"


def test_safety_capability_table_blocks_unlisted_commands():
    from hub.agents.base import Action, Expectation
    from hub.agents.safety import Safety
    from hub.core.bus import EventBus
    from hub.twin.graph import KnowledgeGraph
    from hub.twin.state import TwinState
    from hub.main import HOUSE_CONFIG

    bus, twin, graph = EventBus(), TwinState(), KnowledgeGraph.load(HOUSE_CONFIG)
    safety = Safety(bus, twin, graph, lambda *a: None)
    rogue = Action(
        command_topic="domora/cmd/gas_valve/open",
        payload={},
        cause="test",
        evidence={},
        expectation=Expectation("x", lambda v: True, "n/a", 1),
    )
    assert safety.check(rogue) is False
    assert rogue.status == "vetoed"


if __name__ == "__main__":
    test_leak_is_detected_closed_and_verified()
    test_stuck_valve_fails_verification_and_escalates()
    test_safety_capability_table_blocks_unlisted_commands()
    print("all 3 loop tests passed")

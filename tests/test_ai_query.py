"""DOMORA AI query engine: every answer must trace to a real number pulled
from a real scenario run — no invented data, no LLM in the loop. Covers
both a "data present" and a "nothing to report / unknown" path per intent,
per the repo's simulation-first + failure-path testing rule.
"""

from hub.main import run, step, wire
from hub.services.ai_query import AIQuery
from hub.services.store import JournalReader


def _stepped_world(scenario, ticks):
    world = wire(scenario, narrate=lambda *a: None)
    for t in range(ticks):
        step(world, t)
    return world


# --- power / NILM -----------------------------------------------------

def test_power_question_reports_real_nilm_breakdown():
    world = _stepped_world("energy", 120)
    ai = AIQuery(world.twin, energy=world.energy)

    ans = ai.ask("why is today's power consumption so high?")

    assert ans.intent == "power"
    assert "kettle" in ans.text
    assert 6.5 <= ans.evidence["energy_wh"]["kettle"] <= 8.0
    assert ans.evidence["power_w"] == world.twin.get("main_panel.power_w")


def test_power_question_before_any_disaggregation_is_honest():
    world = _stepped_world("energy", 3)  # a live wattage reading, no edges settled yet
    ai = AIQuery(world.twin, energy=world.energy)

    ans = ai.ask("what's my energy usage?")

    assert ans.intent == "power"
    assert "haven't disaggregated" in ans.text


# --- leak / health (failure path from the flagship stuck scenario) ----

def test_leak_question_true_during_active_leak():
    world = _stepped_world("stuck", 60)  # escalation happens at t=56
    ai = AIQuery(world.twin)

    ans = ai.ask("is there a leak?")

    assert ans.intent == "leak"
    assert ans.evidence["leak_suspected"] is True
    assert "leak is suspected" in ans.text


def test_leak_question_false_at_start():
    world = _stepped_world("stuck", 5)
    ai = AIQuery(world.twin)

    ans = ai.ask("any leaks right now?")

    assert ans.evidence["leak_suspected"] is False
    assert "No leak" in ans.text


def test_health_question_flags_the_suspect_valve():
    world = _stepped_world("stuck", 60)
    ai = AIQuery(world.twin)

    ans = ai.ask("which appliance is becoming unhealthy?")

    assert ans.intent == "health"
    assert "main_valve" in ans.evidence["suspects"]


def test_health_question_clean_when_nothing_suspect():
    world = _stepped_world("leak", 5)  # loop hasn't failed anything yet
    ai = AIQuery(world.twin)

    ans = ai.ask("is anything degrading?")

    assert ans.evidence["suspects"] == []
    assert "healthy" in ans.text


# --- water usage + "what changed while away" need a real journal ------

def test_water_usage_integrates_real_journal_flow(tmp_path):
    db = tmp_path / "journal.db"
    run(scenario="leak", quiet=True, journal_db=str(db))
    reader = JournalReader(db)
    world = _stepped_world("leak", 5)  # twin only used for the no-journal fallback shape
    ai = AIQuery(world.twin, journal=reader)

    ans = ai.ask("how much water was used yesterday?")

    assert ans.intent == "water_usage"
    assert ans.evidence["liters"] > 0
    assert "ticks" in ans.text  # honest: no calendar-day concept yet
    reader.close()


def test_water_usage_without_journal_falls_back_to_live_flow():
    world = _stepped_world("leak", 5)
    ai = AIQuery(world.twin)  # no journal attached

    ans = ai.ask("how much water did we use?")

    assert "don't have a recorded journal" in ans.text
    assert "flow_lpm" in ans.evidence


def test_away_question_lists_the_leak_incident(tmp_path):
    db = tmp_path / "journal.db"
    run(scenario="leak", quiet=True, journal_db=str(db))  # house is empty the whole run
    reader = JournalReader(db)
    world = _stepped_world("leak", 5)
    ai = AIQuery(world.twin, journal=reader)

    ans = ai.ask("what changed while I was away?")

    assert ans.intent == "away"
    assert ans.evidence["events"], "the leak dispatch/verify chain must show up"
    topics = [e["topic"] for e in ans.evidence["events"]]
    assert "domora/act/dispatched" in topics and "domora/verify/confirmed" in topics
    reader.close()


def test_away_question_without_journal_is_honest():
    world = _stepped_world("leak", 5)
    ai = AIQuery(world.twin)

    ans = ai.ask("what happened while I was out?")

    assert "can't replay" in ans.text


# --- explicitly out-of-scope + fully unknown ---------------------------

def test_simulation_request_names_itself_not_implemented():
    world = _stepped_world("leak", 5)
    ai = AIQuery(world.twin)

    ans = ai.ask("what will happen if I leave the pump on?")

    assert ans.intent == "simulation_not_implemented"


def test_unmatched_question_is_honest_not_hallucinated():
    world = _stepped_world("leak", 5)
    ai = AIQuery(world.twin)

    ans = ai.ask("what is the safest temperature for this room?")

    assert ans.intent == "unknown"
    assert "don't have data" in ans.text

"""The /ai HTTP endpoint: DOMORA Studio's chat screen talks to this, not to
ai_query.py directly. Exercises the real wiring — DashboardServer handing
its live twin/energy/journal to AIQuery on each POST — over a real socket.
"""

import json
import threading
import time
import urllib.error
import urllib.request

from hub.main import step, wire
from hub.services import api


def _post_ai(port, message):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/ai",
        data=json.dumps({"message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_ai_endpoint_answers_from_the_live_energy_agent():
    world = wire("energy", narrate=lambda *a: None)
    for t in range(120):
        step(world, t)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0,
                                 energy=world.energy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    body = _post_ai(server.port, "why is power high right now?")

    assert body["intent"] == "power"
    assert "kettle" in body["text"]
    assert 6.5 <= body["evidence"]["energy_wh"]["kettle"] <= 8.0


def test_nilm_endpoint_serves_the_real_ledger():
    world = wire("energy", narrate=lambda *a: None)
    for t in range(120):
        step(world, t)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0,
                                 energy=world.energy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    req = urllib.request.Request(f"http://127.0.0.1:{server.port}/nilm")
    with urllib.request.urlopen(req, timeout=3) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    assert 6.5 <= body["energy_wh"]["kettle"] <= 8.0
    assert len(body["clusters"]) == 3, "matches the server's own ground truth (tests/test_nilm.py)"


def test_nilm_endpoint_without_energy_agent_is_404():
    world = wire("leak", narrate=lambda *a: None)  # water scenario: no EnergySense wired to power data
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    req = urllib.request.Request(f"http://127.0.0.1:{server.port}/nilm")
    try:
        urllib.request.urlopen(req, timeout=3)
        assert False, "expected 404 when no energy agent is attached"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_graph_endpoint_serves_the_real_house_knowledge_graph():
    world = wire("leak", narrate=lambda *a: None)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0,
                                 graph=world.graph)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    req = urllib.request.Request(f"http://127.0.0.1:{server.port}/graph")
    with urllib.request.urlopen(req, timeout=3) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    asset_ids = {a["id"] for a in body["assets"]}
    assert "main_valve" in asset_ids and "water_tank" in asset_ids, "real assets from hub/config/house.json"
    assert any(e["rel"] == "feeds" for e in body["edges"]), "real typed edges, not fabricated"


def test_graph_endpoint_without_graph_is_404():
    world = wire("leak", narrate=lambda *a: None)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    req = urllib.request.Request(f"http://127.0.0.1:{server.port}/graph")
    try:
        urllib.request.urlopen(req, timeout=3)
        assert False, "expected 404 when no graph is attached"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_ai_endpoint_without_energy_agent_still_answers_leak_questions():
    world = wire("stuck", narrate=lambda *a: None)
    for t in range(60):
        step(world, t)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.05)

    body = _post_ai(server.port, "is there a leak?")

    assert body["intent"] == "leak"
    assert body["evidence"]["leak_suspected"] is True

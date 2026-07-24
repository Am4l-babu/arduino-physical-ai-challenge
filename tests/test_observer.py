"""Observer range-checking on the ENV node's real topic contract.

nodes/env_node/env_node.ino publishes domora/env1/living/temp_c etc. — these
ranges didn't exist before the firmware did. A sensor that lies (or a wiring
fault feeding garbage ADC counts) must be quarantined loudly, never trusted
into the twin silently (hub/agents/observer.py's whole reason to exist).
"""

from hub.agents.observer import Observer
from hub.core.bus import EventBus
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState
from hub.main import HOUSE_CONFIG


def _make_observer():
    bus, twin = EventBus(), TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)
    return Observer(bus, twin, graph, lambda *a: None), bus, twin


def test_valid_env_readings_reach_the_twin():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/temp_c", {"value": 24.5})
    bus.publish("domora/env1/living/humidity_pct", {"value": 55.0})
    bus.publish("domora/env1/living/lux", {"value": 300.0})
    bus.publish("domora/env1/living/door", {"value": 1})
    assert twin.get("living.temp_c") == 24.5
    assert twin.get("living.humidity_pct") == 55.0
    assert twin.get("living.lux") == 300.0
    assert twin.get("living.door") == 1
    assert obs.rejected == 0


def test_impossible_temperature_is_quarantined_not_trusted():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/temp_c", {"value": 512.0})  # e.g. a bad I2C read
    assert twin.get("living.temp_c") is None, "an out-of-range reading must never reach the twin"
    assert obs.rejected == 1
    assert twin.get("health.env1.temp_c") == "suspect"


def test_impossible_humidity_is_quarantined():
    obs, bus, twin = _make_observer()
    bus.publish("domora/env1/living/humidity_pct", {"value": -5.0})
    assert twin.get("living.humidity_pct") is None
    assert obs.rejected == 1

"""End-to-end over a REAL broker: field node and hub share nothing but MQTT.

Spawns a private mosquitto on a test port, puts the VirtualHouse on its own
bus behind a role="node" bridge (exactly the shape of ESP32 firmware), the
agents on another bus behind a role="hub" bridge, and proves the leak loop
closes across the wire: sensor -> broker -> twin -> plan -> cmd -> broker ->
valve -> sensor -> VERIFIED.
"""

import socket
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("paho.mqtt.client")

from hub.agents.actor import Actor
from hub.agents.observer import Observer
from hub.agents.planner import Planner
from hub.agents.predictor import Predictor
from hub.agents.safety import Safety
from hub.agents.understander import Understander
from hub.agents.verifier import Verifier
from hub.core.bus import EventBus
from hub.main import HOUSE_CONFIG
from hub.services.mqtt_bridge import MqttBridge
from hub.twin.graph import KnowledgeGraph
from hub.twin.state import TwinState
from sim.virtual_house import VirtualHouse

MOSQUITTO = Path(r"C:\Program Files\mosquitto\mosquitto.exe")
PORT = 18840

pytestmark = pytest.mark.skipif(not MOSQUITTO.exists(), reason="mosquitto not installed")


@pytest.fixture
def broker(tmp_path):
    conf = tmp_path / "mosq.conf"
    conf.write_text(f"listener {PORT} 127.0.0.1\nallow_anonymous true\n", encoding="utf-8")
    proc = subprocess.Popen([str(MOSQUITTO), "-c", str(conf)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", PORT), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("mosquitto did not open its port")
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_leak_loop_closes_over_real_mqtt(broker):
    # --- field side: what an ESP32 node is ---
    field_bus = EventBus()
    house = VirtualHouse(field_bus)
    node_bridge = MqttBridge(field_bus, role="node", port=PORT, client_id="fp1")

    # --- hub side: shares nothing with the field but the broker ---
    hub_bus = EventBus()
    twin = TwinState()
    graph = KnowledgeGraph.load(HOUSE_CONFIG)
    quiet = lambda *a: None  # noqa: E731
    Observer(hub_bus, twin, graph, quiet)
    safety = Safety(hub_bus, twin, graph, quiet)
    actor = Actor(hub_bus, twin, graph, quiet)
    ticking = [
        Understander(hub_bus, twin, graph, quiet),
        Predictor(hub_bus, twin, graph, quiet),
        Planner(hub_bus, twin, graph, quiet, safety=safety),
        verifier := Verifier(hub_bus, twin, graph, quiet, actor=actor),
    ]
    hub_bridge = MqttBridge(hub_bus, role="hub", port=PORT, client_id="hub")

    assert node_bridge.wait_ready() and hub_bridge.wait_ready()
    time.sleep(0.3)  # let QoS1 subscriptions settle

    try:
        for t in range(90):
            node_bridge.pump()          # deliver pending commands to the "valve"
            house.tick(t)               # field publishes sensor readings
            time.sleep(0.02)            # broker round-trip
            twin.now = t
            hub_bridge.pump()           # readings enter the twin
            for agent in ticking:
                agent.tick(t)
            if verifier.confirmed:
                break
    finally:
        node_bridge.close()
        hub_bridge.close()

    assert len(verifier.confirmed) == 1, "leak action must be verified across a real broker"
    assert not house.valve_open, "the physical valve actually closed"
    assert twin.get("tank.line.flow_lpm") == 0.0

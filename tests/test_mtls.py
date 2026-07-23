"""mTLS + ACL tests: the broker must accept certified nodes, reject
uncertified ones, and confine each identity to its own topic namespace.

Security that isn't tested is decoration (spec §17): a stolen node cert
must be a contained blast radius, and these tests are the proof.
"""

import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("paho.mqtt.client")
pytest.importorskip("cryptography")
import paho.mqtt.client as mqtt

from hub.core.bus import EventBus
from hub.services.mqtt_bridge import MqttBridge
from tools.gen_certs import provision

MOSQUITTO = Path(r"C:\Program Files\mosquitto\mosquitto.exe")
PORT = 18843

pytestmark = pytest.mark.skipif(not MOSQUITTO.exists(), reason="mosquitto not installed")


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    return provision(tmp_path_factory.mktemp("certs"), nodes=["fp1"])


@pytest.fixture
def tls_broker(pki, tmp_path):
    acl = tmp_path / "acl.txt"
    acl.write_text(
        "user hub\n"
        "topic readwrite domora/#\n"
        "\n"
        "user fp1\n"
        "topic write domora/fp1/#\n"
        "topic read domora/cmd/#\n",
        encoding="utf-8",
    )
    conf = tmp_path / "mosq_tls.conf"
    conf.write_text(
        f"listener {PORT} 127.0.0.1\n"
        f"cafile {pki / 'ca.pem'}\n"
        f"certfile {pki / 'broker.pem'}\n"
        f"keyfile {pki / 'broker.key'}\n"
        "require_certificate true\n"
        "use_identity_as_username true\n"
        "allow_anonymous false\n"
        f"acl_file {acl}\n",
        encoding="utf-8",
    )
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
            pytest.fail("TLS broker did not open its port")
        yield pki
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _tls_params(pki: Path, identity: str) -> dict:
    return {
        "ca_certs": str(pki / "ca.pem"),
        "certfile": str(pki / f"{identity}.pem"),
        "keyfile": str(pki / f"{identity}.key"),
    }


def _bridged_pair(pki):
    field_bus, hub_bus = EventBus(), EventBus()
    node = MqttBridge(field_bus, role="node", host="localhost", port=PORT,
                      client_id="fp1", tls=_tls_params(pki, "fp1"))
    hub = MqttBridge(hub_bus, role="hub", host="localhost", port=PORT,
                     client_id="hub", tls=_tls_params(pki, "hub"))
    assert node.wait_ready() and hub.wait_ready()
    time.sleep(0.3)
    return field_bus, hub_bus, node, hub


def test_certified_nodes_roundtrip_over_tls(tls_broker):
    field_bus, hub_bus, node, hub = _bridged_pair(tls_broker)
    received = []
    hub_bus.subscribe("domora/#", lambda t, p: received.append((t, p)))
    try:
        field_bus.publish("domora/fp1/tank/flow_lpm", {"value": 3.5})
        for _ in range(50):
            hub.pump()
            if received:
                break
            time.sleep(0.05)
    finally:
        node.close()
        hub.close()
    assert received == [("domora/fp1/tank/flow_lpm", {"value": 3.5})]


def test_client_without_certificate_is_rejected(tls_broker):
    connected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="intruder")
    client.tls_set(ca_certs=str(tls_broker / "ca.pem"))  # trusts broker, offers no identity
    client.on_connect = lambda *a, **k: connected.set()
    try:
        client.connect("localhost", PORT)
        client.loop_start()
        rejected = not connected.wait(timeout=2.0)
    except (ssl.SSLError, ConnectionError, OSError):
        rejected = True  # handshake refused outright — also a pass
    finally:
        client.loop_stop()
    assert rejected, "a client with no certificate must never reach CONNACK"


def test_acl_confines_node_to_its_own_namespace(tls_broker):
    field_bus, hub_bus, node, hub = _bridged_pair(tls_broker)
    received = []
    hub_bus.subscribe("domora/#", lambda t, p: received.append(t))
    try:
        # fp1 impersonates another node's namespace, then uses its own
        field_bus.publish("domora/env1/living/radar", {"value": 1})
        field_bus.publish("domora/fp1/tank/flow_lpm", {"value": 1.0})
        deadline = time.time() + 2.0
        while time.time() < deadline:
            hub.pump()
            time.sleep(0.05)
    finally:
        node.close()
        hub.close()
    assert "domora/fp1/tank/flow_lpm" in received, "own namespace must flow"
    assert "domora/env1/living/radar" not in received, \
        "foreign namespace must be dropped by the broker ACL"

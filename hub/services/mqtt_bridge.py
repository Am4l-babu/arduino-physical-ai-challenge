"""Bridge between the in-process EventBus and a real MQTT broker.

The agents must not notice the difference between simulation and hardware —
same topics, same payloads. Two roles, with disjoint direction filters so a
message can never loop:

  role="hub"   outbound: domora/cmd/#  (actuation toward the field)
               inbound:  data topics   (sensor readings from the field)
  role="node"  outbound: data topics   (this is what an ESP32 does)
               inbound:  domora/cmd/#

Thread-safety: paho delivers messages on its own network thread; they are
queued and only enter the EventBus when the owner calls pump() from its
tick loop. The twin is single-threaded by construction.
"""

import json
import queue
import threading

try:
    import paho.mqtt.client as mqtt
    HAVE_PAHO = True
except ImportError:  # the core runtime must not require paho
    HAVE_PAHO = False

CONTROL_NAMESPACES = {"cmd", "plan", "verify", "act", "alert"}


def _is_control(topic: str) -> bool:
    parts = topic.split("/")
    return len(parts) > 1 and parts[1] in CONTROL_NAMESPACES


def _is_cmd(topic: str) -> bool:
    parts = topic.split("/")
    return len(parts) > 1 and parts[1] == "cmd"


class MqttBridge:
    def __init__(self, bus, role: str, host: str = "127.0.0.1", port: int = 1883,
                 client_id: str = None, tls: dict = None) -> None:
        """`tls`: kwargs for paho's tls_set, e.g. dict(ca_certs=..., certfile=...,
        keyfile=...) — the per-node identity from tools/gen_certs.py."""
        if not HAVE_PAHO:
            raise RuntimeError("paho-mqtt is not installed; pip install paho-mqtt")
        assert role in ("hub", "node")
        self.bus = bus
        self.role = role
        self._inbox: "queue.Queue" = queue.Queue()
        self._ready = threading.Event()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if tls:
            self.client.tls_set(**tls)
        self.client.on_connect = self._on_connect
        self.client.on_message = lambda c, u, msg: self._inbox.put((msg.topic, msg.payload))
        bus.subscribe("domora/#", self._on_local)
        self.client.connect(host, port)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        client.subscribe("domora/cmd/#" if self.role == "node" else "domora/#", qos=1)
        self._ready.set()

    def wait_ready(self, timeout: float = 5.0) -> bool:
        return self._ready.wait(timeout)

    # local bus -> broker
    def _on_local(self, topic: str, payload: dict) -> None:
        outbound = _is_cmd(topic) if self.role == "hub" else not _is_control(topic)
        if outbound:
            self.client.publish(topic, json.dumps(payload, default=str), qos=1)

    # broker -> local bus (drained from the owner's tick loop)
    def pump(self) -> int:
        delivered = 0
        while True:
            try:
                topic, raw = self._inbox.get_nowait()
            except queue.Empty:
                return delivered
            inbound = not _is_control(topic) if self.role == "hub" else _is_cmd(topic)
            if not inbound:
                continue  # own echo or foreign namespace
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                continue  # malformed payloads never reach the agents
            self.bus.publish(topic, payload)
            delivered += 1

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

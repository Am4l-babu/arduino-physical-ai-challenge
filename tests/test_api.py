"""Dashboard API: a real WebSocket client watches the closed loop over the wire.

Exercises the stdlib server end to end — handshake, snapshot replay, and the
live event stream — on both the success path (leak: loop closes, verified) and
the failure path (stuck valve: verification fails, escalates). No browser, no
extra dependency: the test speaks RFC 6455 itself.
"""

import base64
import json
import os
import socket
import threading
import time
import urllib.request

from hub.main import wire, step
from hub.services import api
from hub.services.store import JournalReader
from hub.core.bus import EventBus
from hub.twin.state import TwinState


def _connect(port):
    """Open a raw socket, do the WebSocket handshake, return (sock, rfile)."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(
        f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        .encode()
    )
    rfile = sock.makefile("rb")
    status = rfile.readline()
    assert b"101" in status, status
    while rfile.readline() not in (b"\r\n", b""):  # drain response headers
        pass
    return sock, rfile


def _drain(sock, rfile, budget=3.0):
    """Read every text frame the server sends until the stream goes quiet."""
    msgs = []
    sock.settimeout(0.4)
    deadline = time.time() + budget
    while time.time() < deadline:
        try:
            opcode, data = api.read_frame(rfile)
        except (socket.timeout, OSError):
            break
        if opcode is None:
            break
        if opcode == 0x1:
            msgs.append(json.loads(data.decode("utf-8")))
    return msgs


def _serve_world(scenario):
    world = wire(scenario, narrate=lambda *a: None)
    server = api.DashboardServer(world.bus, world.twin, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return world, server


def _run_and_collect(world, sock, rfile, ticks=120):
    """Tick the world in the background while the client drains concurrently."""
    def _tick():
        for t in range(ticks):
            step(world, t)
            time.sleep(0.002)
    t = threading.Thread(target=_tick)
    t.start()
    msgs = _drain(sock, rfile, budget=6.0)
    t.join(timeout=5)
    return msgs


def test_leak_loop_streams_and_verifies():
    world, server = _serve_world("leak")
    try:
        sock, rfile = _connect(server.port)
        first = api.read_frame(rfile)          # snapshot proves the handshake worked
        assert json.loads(first[1].decode())["type"] == "snapshot"
        time.sleep(0.1)                        # let registration complete

        msgs = _run_and_collect(world, sock, rfile)
        topics = [m.get("topic") for m in msgs if m.get("type") == "event"]
        assert "domora/plan/action" in topics
        assert "domora/verify/confirmed" in topics

        # The action object survives serialization with its expectation intact.
        plan = next(m for m in msgs if m.get("topic") == "domora/plan/action")
        action = plan["payload"]["action"]
        assert action["cause"] == "leak:main_line"
        assert "flow" in action["expectation"]["describe"]

        # Twin point updates reached the client too.
        assert any(m.get("type") == "point" for m in msgs)
        sock.close()
    finally:
        server.shutdown()


def test_stuck_valve_streams_escalation():
    world, server = _serve_world("stuck")
    try:
        sock, rfile = _connect(server.port)
        api.read_frame(rfile)                  # snapshot
        time.sleep(0.1)

        msgs = _run_and_collect(world, sock, rfile)
        alerts = [m for m in msgs if str(m.get("topic", "")).startswith("domora/alert")]
        assert alerts, "stuck valve must escalate a critical alert over the wire"
        assert any("unverified" in (m["payload"].get("reason", "")) for m in alerts)
        sock.close()
    finally:
        server.shutdown()


def _record(scenario, db):
    world = wire(scenario, lambda *a: None, journal_db=str(db))
    for t in range(120):
        step(world, t)
    world.store.close()


def test_journal_playback_reconstructs_incident(tmp_path):
    db = tmp_path / "stuck.db"
    _record("stuck", db)

    reader = JournalReader(str(db))
    tl = reader.timeline()
    tmax = reader.t_max()
    reader.close()

    assert tmax > 0
    assert [f["t"] for f in tl] == sorted(f["t"] for f in tl)  # time-ordered

    disp = [f for f in tl if f.get("topic") == "domora/act/dispatched"]
    assert disp, "the dispatched shutoff must survive into the replay"
    assert disp[0]["payload"]["action"]["cause"] == "leak:main_line"

    alerts = [f for f in tl if str(f.get("topic", "")).startswith("domora/alert")]
    assert any("unverified" in f["payload"].get("reason", "") for f in alerts)
    assert any(f["type"] == "point" for f in tl), "twin history must be recoverable"


def test_playback_endpoint_serves_timeline(tmp_path):
    db = tmp_path / "leak.db"
    _record("leak", db)

    server = api.DashboardServer(EventBus(), TwinState(), host="127.0.0.1",
                                 port=0, journal_path=str(db))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        data = json.loads(urllib.request.urlopen(base + "/playback.json").read())
        assert data["t_max"] > 0 and data["timeline"]
        # the leak run closes its loop — the confirmation is in the recorded timeline
        assert any(f.get("topic") == "domora/verify/confirmed" for f in data["timeline"])
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "DOMORA" in page
    finally:
        server.shutdown()

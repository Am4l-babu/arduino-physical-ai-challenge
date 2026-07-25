"""Dashboard API — live twin + event stream over a stdlib-only WebSocket.

Served straight from the hub so a judge's phone needs no install and the
hub needs no extra dependency (it must run on a 2 GB UNO Q). No FastAPI, no
uvicorn: just http.server + a minimal RFC 6455 WebSocket, consistent with
the repo's "stdlib in core" rule.

The server taps the same bus + twin the agents use. Every bus event and
every twin point-update is serialized to JSON and broadcast to connected
browsers; a bounded history is replayed to late-joining clients so a phone
opened after the leak incident still sees the whole story.

    python -m hub.services.api --scenario stuck    # watch the flagship demo
"""

import base64
import hashlib
import json
import queue
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from hub.agents.base import Action, Expectation
from hub.services.ai_query import AIQuery
from hub.twin.state import Point

_WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboard" / "index.html"
_STUDIO_DIR = (Path(__file__).resolve().parent.parent.parent / "studio").resolve()

HISTORY_LIMIT = 500

_STUDIO_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
}


def _studio_file(rel_path: str):
    """Resolve a /studio/... request under studio/, refusing path-traversal escapes."""
    rel = rel_path.lstrip("/") or "index.html"
    candidate = (_STUDIO_DIR / rel).resolve()
    try:
        candidate.relative_to(_STUDIO_DIR)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


# --- JSON serialization of hub objects ------------------------------------

def _default(o):
    """Render hub dataclasses as plain dicts; drop callables (predicates)."""
    if isinstance(o, Action):
        return {
            "__type": "action", "id": o.id, "command_topic": o.command_topic,
            "cause": o.cause, "evidence": o.evidence, "status": o.status,
            "retries": o.retries, "dispatched_at": o.dispatched_at,
            "expectation": o.expectation,
        }
    if isinstance(o, Expectation):
        return {"point": o.point, "describe": o.describe,
                "deadline_ticks": o.deadline_ticks}
    if isinstance(o, Point):
        return {"value": o.value, "t": o.t, "source": o.source,
                "confidence": o.confidence}
    if callable(o):
        return None
    return str(o)


def dumps(obj) -> str:
    return json.dumps(obj, default=_default)


# --- Minimal RFC 6455 WebSocket frame codec -------------------------------

def encode_frame(text: str) -> bytes:
    """Server->client text frame (unmasked)."""
    payload = text.encode("utf-8")
    header = bytearray([0x81])  # FIN + text opcode
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + payload


def read_frame(rfile):
    """Read one client->server frame. Returns (opcode, bytes) or (None, None) on EOF."""
    b = rfile.read(2)
    if len(b) < 2:
        return None, None
    opcode = b[0] & 0x0F
    masked = b[1] & 0x80
    length = b[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", rfile.read(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", rfile.read(8))[0]
    mask = rfile.read(4) if masked else b"\x00\x00\x00\x00"
    data = bytearray(rfile.read(length))
    if masked:
        for i in range(length):
            data[i] ^= mask[i % 4]
    return opcode, bytes(data)


# --- The server -----------------------------------------------------------

class DashboardServer(ThreadingHTTPServer):
    """Serves the dashboard page and a live WebSocket bound to a bus + twin."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bus, twin, host="0.0.0.0", port=8080, journal_path=None, energy=None, graph=None):
        super().__init__((host, port), _Handler)
        self.bus = bus
        self.twin = twin
        self.energy = energy  # hub.agents.energy.EnergySense, for DOMORA AI's power intent
        self.graph = graph    # hub.twin.graph.KnowledgeGraph, for GET /graph (Studio's Settings page)
        self._clients = set()
        self._clients_lock = threading.Lock()
        self._history = []
        self._history_lock = threading.Lock()

        # Kept open (not just used to build the playback blob) so DOMORA AI
        # can answer journal-backed questions (water usage, "while away")
        # against a recorded run in --playback mode.
        self.journal = None
        self.playback = None
        if journal_path is not None:
            from hub.services.store import JournalReader
            self.journal = JournalReader(journal_path)
            self.playback = dumps({"timeline": self.journal.timeline(),
                                   "t_max": self.journal.t_max()}).encode("utf-8")

        bus.subscribe("#", self._on_event)
        prior = twin.on_set
        def _hook(key, p):
            if prior is not None:
                prior(key, p)
            self._on_point(key, p)
        twin.on_set = _hook

    @property
    def port(self) -> int:
        return self.server_address[1]

    # --- fan-out ---
    def _record_and_broadcast(self, msg: dict) -> None:
        frame = encode_frame(dumps(msg))
        with self._history_lock:
            self._history.append(frame)
            if len(self._history) > HISTORY_LIMIT:
                del self._history[0]
        with self._clients_lock:
            dead = []
            for c in self._clients:
                if not c.send(frame):
                    dead.append(c)
            for c in dead:
                self._clients.discard(c)

    def _on_event(self, topic: str, payload: dict) -> None:
        self._record_and_broadcast({
            "type": "event", "topic": topic, "payload": payload,
            "t": self.twin.now,
        })

    def _on_point(self, key: str, p: Point) -> None:
        self._record_and_broadcast({
            "type": "point", "key": key, "value": p.value, "t": p.t,
            "source": p.source, "confidence": p.confidence,
        })

    # --- client lifecycle ---
    def register(self, client) -> None:
        # Replay current twin snapshot + event history to the new client.
        snapshot = {
            "type": "snapshot", "t": self.twin.now,
            "points": {k: {"value": pt.value, "t": pt.t, "source": pt.source,
                           "confidence": pt.confidence}
                       for k, pt in self.twin.points.items()},
        }
        client.send(encode_frame(dumps(snapshot)))
        with self._history_lock:
            backlog = list(self._history)
        for frame in backlog:
            client.send(frame)
        with self._clients_lock:
            self._clients.add(client)

    def unregister(self, client) -> None:
        with self._clients_lock:
            self._clients.discard(client)
        client.close()


class _WSClient:
    """One connected browser, fed by its own bounded queue + sender thread.

    A slow phone must never stall the hub's agent loop, so broadcasts only
    enqueue (never block); if a client falls too far behind, its oldest
    frames are dropped to keep the latest state flowing.
    """

    QUEUE_MAX = 2000

    def __init__(self, conn):
        self.conn = conn
        self.q: "queue.Queue[bytes]" = queue.Queue(maxsize=self.QUEUE_MAX)
        self.alive = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def send(self, frame: bytes) -> bool:
        if not self.alive:
            return False
        try:
            self.q.put_nowait(frame)
        except queue.Full:
            try:                        # drop oldest, keep the newest state
                self.q.get_nowait()
                self.q.put_nowait(frame)
            except queue.Empty:
                pass
        return True

    def _run(self) -> None:
        while self.alive:
            frame = self.q.get()
            if frame is None:
                break
            try:
                self.conn.sendall(frame)
            except OSError:
                self.alive = False
                break

    def close(self) -> None:
        self.alive = False
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence default access logging
        pass

    def do_GET(self):
        if self.path.split("?")[0] == "/ws":
            self._serve_ws()
        elif self.path in ("/", "/index.html"):
            self._serve_file(_DASHBOARD, "text/html; charset=utf-8")
        elif self.path == "/health":
            self._serve_bytes(b"ok", "text/plain")
        elif self.path.split("?")[0] == "/playback.json":
            if self.server.playback is None:
                self.send_error(404)
            else:
                self._serve_bytes(self.server.playback, "application/json")
        elif self.path.split("?")[0] == "/studio" or self.path.split("?")[0].startswith("/studio/"):
            self._serve_studio()
        elif self.path.split("?")[0] == "/history":
            self._serve_history()
        elif self.path.split("?")[0] == "/nilm":
            self._serve_nilm()
        elif self.path.split("?")[0] == "/graph":
            self._serve_graph()
        else:
            self.send_error(404)

    def _serve_graph(self):
        # The real house knowledge graph (hub/config/house.json via
        # hub.twin.graph.KnowledgeGraph) — what Studio's Settings page shows
        # as rooms/nodes. Not a separate config file the UI reads directly:
        # this way it always reflects whatever graph the live world actually
        # loaded, the same one the planner reasons over.
        if self.server.graph is None:
            self.send_error(404)
            return
        graph = self.server.graph
        self._serve_bytes(
            dumps({"assets": list(graph.assets.values()), "edges": graph.edges}).encode("utf-8"),
            "application/json",
        )

    def _serve_nilm(self):
        # The authoritative NILM ledger — hub/agents/energy.py's own
        # clusters/energy_wh dicts, the same ground truth tests/test_nilm.py
        # and hub/services/ai_query.py's power intent already trust. Not
        # reconstructed from twin points client-side (see studio/core/twin.js
        # for why that's unsound: a relabelled cluster's old points never
        # retire, so point-scanning can double-count or drop appliances).
        if self.server.energy is None:
            self.send_error(404)
            return
        self._serve_bytes(dumps(self.server.energy.report()).encode("utf-8"), "application/json")

    def _serve_history(self):
        # Journal-backed point history — only available in --playback mode
        # (self.server.journal is a live JournalReader there). Studio's
        # charts fall back to their own client-side session buffer when
        # this 404s, rather than pretending multi-day history exists.
        if self.server.journal is None:
            self.send_error(404)
            return
        query = parse_qs(urlsplit(self.path).query)
        key = (query.get("key") or [None])[0]
        if not key:
            self.send_error(400)
            return
        try:
            limit = int((query.get("limit") or ["500"])[0])
        except ValueError:
            self.send_error(400)
            return
        rows = self.server.journal.db.execute(
            "SELECT t, value FROM points_journal WHERE key=? ORDER BY t", (key,)
        ).fetchall()
        points = [[t, json.loads(v)] for t, v in rows[-limit:]]
        self._serve_bytes(dumps({"key": key, "points": points}).encode("utf-8"), "application/json")

    def _serve_studio(self):
        rel = self.path.split("?")[0][len("/studio"):]
        path = _studio_file(rel)
        if path is None:
            self.send_error(404)
            return
        ctype = _STUDIO_CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        self._serve_file(path, ctype)

    def do_POST(self):
        if self.path.split("?")[0] == "/ai":
            self._serve_ai()
        else:
            self.send_error(404)

    def _serve_ai(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            message = json.loads(raw.decode("utf-8")).get("message", "")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            self.send_error(400)
            return
        answer = AIQuery(self.server.twin, energy=self.server.energy,
                         journal=self.server.journal).ask(message)
        self._serve_bytes(
            dumps({"text": answer.text, "evidence": answer.evidence, "intent": answer.intent})
            .encode("utf-8"),
            "application/json",
        )

    def _serve_file(self, path: Path, ctype: str):
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self._serve_bytes(body, ctype)

    def _serve_bytes(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_ws(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400)
            return
        accept = base64.b64encode(
            hashlib.sha1((key + _WS_MAGIC).encode()).digest()
        ).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        client = _WSClient(self.connection)
        self.server.register(client)
        try:
            while True:
                opcode, _ = read_frame(self.rfile)
                if opcode is None or opcode == 0x8:  # EOF or close
                    break
        except OSError:
            pass
        finally:
            self.server.unregister(client)
        self.close_connection = True


def serve_playback(journal_path, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Serve a recorded journal for scrub-back playback (no live world)."""
    from hub.core.bus import EventBus
    from hub.twin.state import TwinState

    server = DashboardServer(EventBus(), TwinState(), host=host, port=port,
                             journal_path=journal_path)
    print(f"--- DOMORA playback on http://localhost:{server.port}  (journal: {journal_path}) ---")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n--- playback stopped ---")


def serve(scenario: str = "stuck", host: str = "0.0.0.0", port: int = 8080,
          ticks: int = 120, tick_hz: float = 3.0, loop: bool = True) -> None:
    """Wire a world, attach the dashboard, and step the scenario in real time."""
    from hub.main import wire, step

    def narrate(t, agent, message):
        print(f"[t={t:03d}] {agent:<12} | {message}")

    world = wire(scenario, narrate)
    server = DashboardServer(world.bus, world.twin, host=host, port=port,
                             energy=world.energy, graph=world.graph)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"--- DOMORA dashboard on http://localhost:{server.port}  (scenario: {scenario}) ---")

    period = 1.0 / tick_hz
    try:
        while True:
            for t in range(ticks):
                step(world, t)
                time.sleep(period)
            if not loop:
                break
            time.sleep(3.0)          # hold the final state, then replay
            world = wire(scenario, narrate)
            server.bus = world.bus   # re-tap the fresh world
            server.twin = world.twin
            server.energy = world.energy
            server.graph = world.graph
            world.bus.subscribe("#", server._on_event)
            prior = world.twin.on_set
            def _hook(key, p, prior=prior):
                if prior is not None:
                    prior(key, p)
                server._on_point(key, p)
            world.twin.on_set = _hook
    except KeyboardInterrupt:
        print("\n--- dashboard stopped ---")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Serve the DOMORA live dashboard")
    parser.add_argument("--scenario",
                        choices=["leak", "stuck", "energy", "dryrun", "dryrun_stuck"],
                        default="stuck")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--hz", type=float, default=3.0, help="ticks per second")
    parser.add_argument("--once", action="store_true", help="run one pass, don't loop")
    parser.add_argument("--playback", metavar="DB", default=None,
                        help="serve a recorded journal (from `hub.main --journal DB`) for scrub-back")
    args = parser.parse_args()
    if args.playback:
        serve_playback(args.playback, port=args.port)
    else:
        serve(scenario=args.scenario, port=args.port, ticks=args.ticks,
              tick_hz=args.hz, loop=not args.once)

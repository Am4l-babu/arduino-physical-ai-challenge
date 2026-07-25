"""GET /history: journal-backed point history for Studio's charts.

Only available in --playback mode (self.server.journal is a live
JournalReader there) — a plain live scenario has no journal attached, and
the endpoint must say so honestly (404) rather than fabricate a history.
"""

import json
import threading
import urllib.error
import urllib.request

from hub.core.bus import EventBus
from hub.main import run
from hub.services import api
from hub.twin.state import TwinState


def _get(port, path):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3)


def test_history_serves_real_journaled_points(tmp_path):
    db = tmp_path / "journal.db"
    run(scenario="leak", quiet=True, journal_db=str(db))

    server = api.DashboardServer(EventBus(), TwinState(), host="127.0.0.1", port=0, journal_path=str(db))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    resp = _get(server.port, "/history?key=tank.line.flow_lpm")
    body = json.loads(resp.read().decode("utf-8"))

    assert body["key"] == "tank.line.flow_lpm"
    assert len(body["points"]) > 50
    ts = [p[0] for p in body["points"]]
    assert ts == sorted(ts), "points must come back in time order"


def test_history_without_journal_is_404():
    server = api.DashboardServer(EventBus(), TwinState(), host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        _get(server.port, "/history?key=tank.line.flow_lpm")
        assert False, "expected 404 when no journal is attached"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_history_missing_key_is_400(tmp_path):
    db = tmp_path / "journal.db"
    run(scenario="leak", quiet=True, journal_db=str(db))
    server = api.DashboardServer(EventBus(), TwinState(), host="127.0.0.1", port=0, journal_path=str(db))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        _get(server.port, "/history")
        assert False, "expected 400 without a key"
    except urllib.error.HTTPError as e:
        assert e.code == 400

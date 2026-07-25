"""DOMORA Studio static serving: the hub's HTTP server hands out studio/
files (no build step, no CDN — see docs/APP_PLAN.md §2) alongside the
existing WebSocket. Exercises real serving over a real socket, plus a
direct check that the path-traversal guard actually refuses an escape.
"""

import threading
import urllib.error
import urllib.request

import pytest

from hub.core.bus import EventBus
from hub.services import api
from hub.twin.state import TwinState


def _serve():
    server = api.DashboardServer(EventBus(), TwinState(), host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _get(port, path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    return urllib.request.urlopen(req, timeout=3)


def test_studio_index_serves_html():
    server = _serve()
    resp = _get(server.port, "/studio/")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("text/html")
    body = resp.read().decode("utf-8")
    assert "DOMORA" in body


def test_studio_serves_nested_js_and_css_with_correct_type():
    server = _serve()

    resp = _get(server.port, "/studio/app.js")
    assert resp.status == 200
    assert "javascript" in resp.headers["Content-Type"]

    resp = _get(server.port, "/studio/core/dom.js")
    assert resp.status == 200
    assert "javascript" in resp.headers["Content-Type"]
    assert b"export function h" in resp.read()

    resp = _get(server.port, "/studio/tokens.css")
    assert resp.status == 200
    assert "text/css" in resp.headers["Content-Type"]


def test_studio_missing_file_is_404():
    server = _serve()
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server.port, "/studio/does-not-exist.js")
    assert exc.value.code == 404


def test_studio_path_traversal_guard_refuses_escape():
    # Exercise the guard directly: it must reject any resolved path outside
    # studio/, not just the specific ../ spelling a client happens to send.
    assert api._studio_file("../CLAUDE.md") is None
    assert api._studio_file("../../hub/services/api.py") is None
    assert api._studio_file("core/../../PROGRESS.md") is None
    # A legitimate nested file still resolves.
    assert api._studio_file("core/dom.js") is not None


def test_dashboard_still_served_at_root_unchanged():
    # The Studio addition must not disturb the existing week-5 dashboard.
    server = _serve()
    resp = _get(server.port, "/")
    assert resp.status == 200
    assert "DOMORA" in resp.read().decode("utf-8")

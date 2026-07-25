"""SQLite journaling (WAL) — the twin's memory and the action audit trail.

Three tables (spec §13: SQLite for everything operational at MVP):
  points_journal  every twin state change, with provenance
  actions         cause -> evidence -> expectation -> outcome, per action
  events          alerts and vetoes as they happened

The store attaches to the bus and the twin; agents don't know it exists.
Stdlib only — this must run on the UNO Q.
"""

import json
import sqlite3
from pathlib import Path

COMMIT_EVERY = 500  # writes per transaction; balances durability vs. throughput


class Store:
    def __init__(self, path) -> None:
        self.path = Path(path)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS points_journal(
                t INTEGER, key TEXT, value TEXT, source TEXT, confidence REAL);
            CREATE INDEX IF NOT EXISTS idx_journal_key_t ON points_journal(key, t);
            CREATE TABLE IF NOT EXISTS actions(
                id INTEGER PRIMARY KEY, t_dispatched INTEGER, topic TEXT,
                cause TEXT, evidence TEXT, expectation TEXT,
                status TEXT, retries INTEGER, t_resolved INTEGER);
            CREATE TABLE IF NOT EXISTS events(t INTEGER, topic TEXT, payload TEXT);
            """
        )
        self._pending_writes = 0

    def attach(self, bus, twin) -> None:
        self._twin = twin
        twin.on_set = self._journal_point
        bus.subscribe("domora/act/dispatched", self._on_dispatched)
        bus.subscribe("domora/verify/confirmed", self._on_confirmed)
        bus.subscribe("domora/alert/#", self._on_alert)

    # -- writers ----------------------------------------------------------
    def _journal_point(self, key, point) -> None:
        self.db.execute(
            "INSERT INTO points_journal VALUES(?,?,?,?,?)",
            (point.t, key, json.dumps(point.value), point.source, point.confidence),
        )
        self._maybe_commit()

    def _on_dispatched(self, topic, payload) -> None:
        a = payload["action"]
        self.db.execute(
            "INSERT OR REPLACE INTO actions VALUES(?,?,?,?,?,?,?,?,?)",
            (a.id, a.dispatched_at, a.command_topic, a.cause,
             json.dumps(a.evidence), a.expectation.describe,
             a.status, a.retries, None),
        )
        self._maybe_commit()

    def _on_confirmed(self, topic, payload) -> None:
        self.db.execute(
            "UPDATE actions SET status='confirmed', t_resolved=? WHERE id=?",
            (self._twin.now, payload["action_id"]),
        )
        self._maybe_commit()

    def _on_alert(self, topic, payload) -> None:
        self.db.execute(
            "INSERT INTO events VALUES(?,?,?)",
            (self._twin.now, topic, json.dumps(payload, default=str)),
        )
        if "action_id" in payload and topic.endswith("critical"):
            self.db.execute(
                "UPDATE actions SET status='failed', t_resolved=? WHERE id=?",
                (self._twin.now, payload["action_id"]),
            )
        self._maybe_commit()

    def _maybe_commit(self) -> None:
        self._pending_writes += 1
        if self._pending_writes >= COMMIT_EVERY:
            self.db.commit()
            self._pending_writes = 0

    # -- lifecycle --------------------------------------------------------
    def stats(self) -> dict:
        rows = {t: self.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("points_journal", "actions", "events")}
        self.db.commit()
        size = 0
        for suffix in ("", "-wal", "-shm"):  # WAL mode: data lives in sidecars until checkpoint
            f = Path(str(self.path) + suffix)
            if f.exists():
                size += f.stat().st_size
        rows["db_bytes"] = size
        return rows

    def close(self) -> dict:
        self.db.commit()
        stats = self.stats()
        self.db.close()
        return stats


class JournalReader:
    """Read-side of the journal: rebuilds a recorded run as a replayable timeline.

    Emits the same frame contract the live WebSocket uses (`type: point` /
    `type: event`), so the dashboard renders playback through exactly the same
    code path as a live incident — no second renderer to keep in sync.
    """

    # within one tick: points settle before the actions/alerts they trigger
    _ORDER = {"point": 0, "event": 1}

    def __init__(self, path) -> None:
        self.path = Path(path)
        # check_same_thread=False: read-only connection, no writes/transactions
        # ever span threads — needed because DashboardServer (ThreadingHTTPServer)
        # opens this once but queries it from whichever thread handles a request.
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)

    def timeline(self) -> list:
        frames = []
        for t, key, value, source, conf in self.db.execute(
                "SELECT t, key, value, source, confidence FROM points_journal"):
            frames.append({"type": "point", "t": t, "key": key,
                           "value": json.loads(value), "source": source,
                           "confidence": conf})

        for (aid, t_disp, topic, cause, evidence, expectation,
             status, retries, t_res) in self.db.execute(
                "SELECT id, t_dispatched, topic, cause, evidence, expectation, "
                "status, retries, t_resolved FROM actions"):
            frames.append({"type": "event", "t": t_disp,
                           "topic": "domora/act/dispatched",
                           "payload": {"action": {
                               "__type": "action", "id": aid, "command_topic": topic,
                               "cause": cause, "evidence": json.loads(evidence),
                               "expectation": {"describe": expectation},
                               "status": status, "retries": retries,
                               "dispatched_at": t_disp}}})
            if status == "confirmed" and t_res is not None:
                frames.append({"type": "event", "t": t_res,
                               "topic": "domora/verify/confirmed",
                               "payload": {"action_id": aid}})

        for t, topic, payload in self.db.execute(
                "SELECT t, topic, payload FROM events"):
            frames.append({"type": "event", "t": t, "topic": topic,
                           "payload": json.loads(payload)})

        frames.sort(key=lambda f: (f["t"], self._ORDER.get(f["type"], 9)))
        return frames

    def t_max(self) -> int:
        rows = [self.db.execute("SELECT MAX(t) FROM points_journal").fetchone()[0],
                self.db.execute("SELECT MAX(t_resolved) FROM actions").fetchone()[0],
                self.db.execute("SELECT MAX(t) FROM events").fetchone()[0]]
        return max([r for r in rows if r is not None], default=0)

    def close(self) -> None:
        self.db.close()

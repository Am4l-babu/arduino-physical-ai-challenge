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

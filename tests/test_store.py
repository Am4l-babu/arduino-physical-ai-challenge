"""Journaling tests: the audit trail must capture the whole causal chain."""

import json
import sqlite3
import threading

from hub.main import run
from hub.services.store import JournalReader


def test_leak_run_is_fully_journaled(tmp_path):
    db = tmp_path / "journal.db"
    s = run(scenario="leak", quiet=True, journal_db=str(db))

    assert s["journal"]["points_journal"] > 500, "every twin change is journaled"
    assert s["journal"]["actions"] == 1

    conn = sqlite3.connect(str(db))
    status, cause, evidence, expectation = conn.execute(
        "SELECT status, cause, evidence, expectation FROM actions").fetchone()
    conn.close()

    assert status == "confirmed"
    assert cause == "leak:main_line"
    assert json.loads(evidence)["fixtures_open"] == 0, "evidence preserved verbatim"
    assert "flow" in expectation, "the expected effect is part of the record"


def test_stuck_run_journals_failure_and_alert(tmp_path):
    db = tmp_path / "journal.db"
    run(scenario="stuck", quiet=True, journal_db=str(db))

    conn = sqlite3.connect(str(db))
    (status,) = conn.execute("SELECT status FROM actions").fetchone()
    alerts = conn.execute(
        "SELECT COUNT(*) FROM events WHERE topic='domora/alert/critical'").fetchone()[0]
    conn.close()

    assert status == "failed"
    assert alerts >= 1


def test_journal_reader_usable_from_a_different_thread(tmp_path):
    # DashboardServer (ThreadingHTTPServer) opens one JournalReader up front
    # but queries it from whichever thread handles a given request — sqlite3
    # connections are thread-affine by default and raise ProgrammingError
    # unless opened with check_same_thread=False. Regression test for that.
    db = tmp_path / "journal.db"
    run(scenario="leak", quiet=True, journal_db=str(db))
    reader = JournalReader(db)

    result = {}
    def query_from_other_thread():
        try:
            result["t_max"] = reader.t_max()
        except Exception as e:  # noqa: BLE001 - want the failure visible, not swallowed
            result["error"] = e

    t = threading.Thread(target=query_from_other_thread)
    t.start()
    t.join(timeout=5)

    assert "error" not in result, f"JournalReader failed off-thread: {result.get('error')}"
    assert result["t_max"] > 0
    reader.close()

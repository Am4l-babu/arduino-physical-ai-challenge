"""Journaling tests: the audit trail must capture the whole causal chain."""

import json
import sqlite3

from hub.main import run


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

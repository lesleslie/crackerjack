"""Durable, commit-keyed storage of per-test run results.

Why this exists
---------------
The team re-runs full test suites repeatedly just to re-establish what the
test status *was*. A ratchet file holds one number (coverage percent) and
the coverage report is gitignored, per-checkout, and overwritten by the next
run - so the answer to "was this repo green at commit X?" is another suite
run, not a lookup.

This store records the per-test outcome of every run, keyed by
``(repo, commit_sha, worktree)``, so that question becomes a query.

Design notes
------------
- **SQLite, not a vector store.** The question is an exact-key lookup
  ("commit abc123 in worktree /w"), not a similarity search.
- **Crackerjack owns this file.** It lives under
  ``data_dir(app="crackerjack")``, not inside Session-Buddy's namespace -
  see ``docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md``.
  Session-Buddy's ``crackerjack_integration.db`` holds a ``test_results``
  table with the same shape, but it has been empty across its entire
  recorded history: the writer only ran when Session-Buddy itself launched
  crackerjack, and its parser could not match modern pytest output.
- **Structured input, not scraped output.** Callers pass normalized test
  dicts (``node_id``, ``status``, ``duration``, ``file_path``,
  ``error_message``), not raw pytest terminal text.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import typing as t
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from crackerjack.utils.path_redaction import redact_path

logger = logging.getLogger(__name__)

#: Statuses counted as failures when deriving the run's failure count.
FAILURE_STATUSES = frozenset({"failed", "error"})

#: Statuses counted as errors (as distinct from assertion failures).
ERROR_STATUSES = frozenset({"error"})

_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        repo TEXT NOT NULL,
        commit_sha TEXT NOT NULL,
        worktree TEXT NOT NULL,
        branch TEXT,
        started_at TIMESTAMP NOT NULL,
        finished_at TIMESTAMP,
        exit_code INTEGER,
        selection_mode TEXT NOT NULL,
        total INTEGER NOT NULL DEFAULT 0,
        passed INTEGER NOT NULL DEFAULT 0,
        failed INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0,
        errors INTEGER NOT NULL DEFAULT 0,
        duration REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS test_results (
        run_id TEXT NOT NULL,
        node_id TEXT NOT NULL,
        status TEXT NOT NULL,
        duration REAL,
        file_path TEXT,
        error_message TEXT,
        PRIMARY KEY (run_id, node_id),
        FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_repo_commit ON runs(repo, commit_sha)",
    "CREATE INDEX IF NOT EXISTS idx_runs_worktree ON runs(worktree)",
)


class RunStateStore:
    """SQLite-backed store of per-test run results.

    All access is synchronous. The store is written from the (synchronous)
    test-manager phase, where a local SQLite write costs microseconds; an
    async caller should wrap these calls in ``loop.run_in_executor``.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._initialized = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._connect() as conn:
            for statement in _SCHEMA_SQL:
                conn.execute(statement)
            conn.commit()
        self._initialized = True

    def record_run(
        self,
        *,
        repo: str,
        commit_sha: str,
        worktree: str,
        branch: str | None,
        started_at: datetime,
        finished_at: datetime,
        exit_code: int,
        selection_mode: str,
        tests: list[dict[str, t.Any]],
    ) -> str:
        """Record one test run and its per-test results.

        Returns the new run id.
        """
        self._ensure_schema()

        run_id = uuid.uuid4().hex
        duration = (finished_at - started_at).total_seconds()

        counts = self._count_statuses(tests)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, repo, commit_sha, worktree, branch, started_at,
                    finished_at, exit_code, selection_mode, total, passed,
                    failed, skipped, errors, duration
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    repo,
                    commit_sha,
                    worktree,
                    branch,
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    exit_code,
                    selection_mode,
                    counts["total"],
                    counts["passed"],
                    counts["failed"],
                    counts["skipped"],
                    counts["errors"],
                    duration,
                ),
            )

            conn.executemany(
                """
                INSERT OR REPLACE INTO test_results
                (run_id, node_id, status, duration, file_path, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(test.get("node_id", "")),
                        str(test.get("status", "")),
                        test.get("duration"),
                        test.get("file_path"),
                        test.get("error_message"),
                    )
                    for test in tests
                ],
            )
            conn.commit()

        logger.info(
            "Recorded run %s for %s@%s in %s: %d tests (%d passed, %d failed)",
            run_id,
            repo,
            commit_sha[:8],
            redact_path(worktree),
            counts["total"],
            counts["passed"],
            counts["failed"],
        )
        return run_id

    def get_run(
        self,
        repo: str,
        commit_sha: str,
        worktree: str | None = None,
    ) -> dict[str, t.Any] | None:
        """Return the most recent run for a commit, or ``None``.

        ``None`` (never an empty dict) means "no recorded run for that
        commit" - a caller must not read that as "the run was empty".
        """
        self._ensure_schema()

        query = "SELECT * FROM runs WHERE repo = ? AND commit_sha = ?"
        params: list[t.Any] = [repo, commit_sha]
        if worktree is not None:
            query += " AND worktree = ?"
            params.append(worktree)
        query += " ORDER BY finished_at DESC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()

        return dict(row) if row is not None else None

    def list_runs(
        self,
        repo: str,
        commit_sha: str,
    ) -> list[dict[str, t.Any]]:
        """Return every recorded run for a commit, newest first."""
        self._ensure_schema()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs
                WHERE repo = ? AND commit_sha = ?
                ORDER BY finished_at DESC
                """,
                (repo, commit_sha),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_test_results(self, run_id: str) -> list[dict[str, t.Any]]:
        """Return the per-test results recorded for a run."""
        self._ensure_schema()

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT node_id, status, duration, file_path, error_message
                FROM test_results
                WHERE run_id = ?
                ORDER BY node_id
                """,
                (run_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_status_map(self, run_id: str) -> dict[str, str]:
        """Return ``{node_id: status}`` for a run - the diffing primitive."""
        return {
            result["node_id"]: result["status"]
            for result in self.get_test_results(run_id)
        }

    @staticmethod
    def _count_statuses(tests: list[dict[str, t.Any]]) -> dict[str, int]:
        counts = {
            "total": len(tests),
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
        }
        for test in tests:
            status = str(test.get("status", "")).lower()
            if status in ERROR_STATUSES:
                counts["errors"] += 1
            if status in FAILURE_STATUSES:
                counts["failed"] += 1
            elif status == "passed":
                counts["passed"] += 1
            elif status in {"skipped", "xfailed"}:
                counts["skipped"] += 1
        return counts


def load_pytest_json_report(path: Path) -> dict[str, t.Any]:
    """Parse a ``pytest-json-report`` file into a normalized shape.

    Returns ``{"tests": [...], "summary": {...}, "available": bool}`` where
    each test carries ``node_id``, ``status``, ``duration``, ``file_path``
    and ``error_message``. ``available`` is False when the file could not
    be read or parsed, which is *different* from a report that legitimately
    contains no tests - the second case is what an incremental run whose
    change affects nothing produces.

    A missing or malformed file yields an empty result rather than raising:
    recording run state must never fail a test run.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        logger.warning("Could not read pytest JSON report at %s", path)
        return {"tests": [], "summary": {}, "available": False}

    if not isinstance(raw, dict):
        return {"tests": [], "summary": {}, "available": False}

    tests: list[dict[str, t.Any]] = []
    for entry in raw.get("tests", []) or []:
        if not isinstance(entry, dict):
            continue
        node_id = str(entry.get("nodeid", ""))
        tests.append(
            {
                "node_id": node_id,
                "status": str(entry.get("outcome", "")).lower(),
                "duration": _report_duration(entry),
                "file_path": _report_file_path(entry, node_id),
                "error_message": _report_error_message(entry),
            }
        )

    summary = raw.get("summary", {}) or {}
    return {
        "tests": tests,
        "summary": summary if isinstance(summary, dict) else {},
        "available": True,
    }


def _report_file_path(entry: dict[str, t.Any], node_id: str) -> str | None:
    """Derive the test file from the report.

    pytest-json-report does not emit a ``location`` key; the file is the
    part of the node id before the first ``::``.
    """
    location = entry.get("location")
    if isinstance(location, list) and location:
        return str(location[0])
    if "::" in node_id:
        return node_id.split("::", 1)[0]
    return node_id or None


def _report_duration(entry: dict[str, t.Any]) -> float | None:
    """Total the test's setup, call and teardown durations.

    pytest-json-report keeps durations inside each phase rather than at
    the top level of the test entry.
    """
    total = 0.0
    found = False
    for phase in ("setup", "call", "teardown"):
        payload = entry.get(phase)
        if not isinstance(payload, dict):
            continue
        duration = payload.get("duration")
        if isinstance(duration, (int, float)):
            total += float(duration)
            found = True
    return total if found else None


def _report_error_message(entry: dict[str, t.Any]) -> str | None:
    for phase in ("call", "setup", "teardown"):
        payload = entry.get(phase)
        if not isinstance(payload, dict):
            continue
        message = payload.get("longrepr")
        if isinstance(message, str) and message.strip():
            return message
    return None

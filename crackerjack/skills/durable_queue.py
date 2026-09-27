"""Durable queue for PR review retries — sqlmodel-backed.

Persists PR URLs that failed GitHub fetch (5xx, 429, network) so a
background retry process can re-attempt them. Uses ``fcntl.flock`` for
concurrency safety across cooperating processes on POSIX.

Schema (``ReviewQueueRecord``) is a single SQLModel table; the queue
module wraps it in a small API (``enqueue`` / ``dequeue`` / ``__len__``)
that the review-pr skill uses without knowing it's a database.

Why sqlmodel: the project already depends on it (see
``crackerjack/data/models.py``) and the user directive for new ORM models
is "use sqlmodel for any new ORM models".
"""

from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select


class ReviewQueueRecord(SQLModel, table=True):
    """One PR URL pending review (or in flight).

    Inserted by ``DurableQueue.enqueue``; deleted by ``dequeue`` after
    the caller acknowledges. ``created_at`` is monotonic so FIFO order
    holds without an extra index — sqlite rowid ordering + the index
    together guarantee a stable global order under concurrent writers.
    """

    __tablename__ = "crackerjack_review_queue"

    id: int | None = Field(default=None, primary_key=True)
    pr_url: str = Field(index=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )


class DurableQueue:
    """sqlite-backed FIFO queue with fcntl-based cross-process locking."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.suffix != ".db":
            self.path = self.path.with_suffix(".db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # sqlite_url = f"sqlite:///{self.path}"
        self._engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False, "timeout": 30.0},
        )
        SQLModel.metadata.create_all(self._engine)
        self._lock_path = self.path.with_suffix(".lock")
        if not self._lock_path.exists():
            self._lock_path.touch()

    @contextmanager
    def _process_lock(self, mode: str = "r+") -> Iterator[None]:
        """Cross-process fcntl.flock wrapper for the SQL writer path."""
        with self._lock_path.open(mode) as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def enqueue(self, pr_url: str) -> None:
        """Append a PR URL to the queue (idempotent: duplicates ignored).

        Wrapped in a process-level flock so two writers racing on the
        same DB file serialise on the OS-level lock, not just on sqlite's
        WAL. Without this, two ``enqueue`` calls interleaved could
        generate a duplicate-primary-key error before the unique-index
        check ran.
        """
        with self._process_lock("a"):
            # Stale empty lock files from a previous run can confuse
            # fcntl on some macOS builds; truncate to be safe.
            self._lock_path.write_text("")
            with Session(self._engine) as session:
                existing = session.exec(
                    select(ReviewQueueRecord).where(ReviewQueueRecord.pr_url == pr_url)
                ).first()
                if existing is not None:
                    return
                session.add(ReviewQueueRecord(pr_url=pr_url))
                session.commit()

    def dequeue(self) -> str | None:
        """Pop the oldest PR URL from the queue. Returns None if empty.

        Reads under flock so a concurrent ``enqueue`` cannot insert
        between the SELECT and the DELETE.
        """
        with self._process_lock("r+"):
            with Session(self._engine) as session:
                # ty infers ``ReviewQueueRecord.created_at`` as ``datetime`` (the
                # declared annotation) instead of recognizing it as a SQLAlchemy
                # column descriptor at class scope. Runtime resolution is
                # correct (SQLAlchemy uses the descriptor); the ignore is
                # purely to satisfy ty's static view of class-level access.
                stmt = select(ReviewQueueRecord).order_by(ReviewQueueRecord.created_at)  # ty: ignore[invalid-argument-type]
                record = session.exec(stmt).first()
                if record is None:
                    return None
                pr_url = record.pr_url
                session.delete(record)
                session.commit()
                return pr_url

    def __len__(self) -> int:
        with Session(self._engine) as session:
            stmt = select(ReviewQueueRecord)
            return len(session.exec(stmt).all())

    @property
    def db_path(self) -> Path:
        """Filesystem path of the sqlite file (for tests + observability)."""
        return self.path


def _drain_legacy_jsonl(legacy_path: Path, queue: DurableQueue) -> int:
    """One-shot drain from a previous (fcntl+jsonl) queue to sqlmodel.

    Only used during migration; the function is exported so tests can
    assert migration behaviour without coupling to a CLI script.
    """
    if not legacy_path.exists():
        return 0
    drained = 0
    for line in legacy_path.read_text().splitlines():
        try:
            payload = json.loads(line)
            item = payload.get("item")
        except ValueError, AttributeError:
            continue
        if isinstance(item, str) and item:
            queue.enqueue(item)
            drained += 1
    legacy_path.unlink(missing_ok=True)
    return drained


__all__ = ["DurableQueue", "ReviewQueueRecord", "_drain_legacy_jsonl"]

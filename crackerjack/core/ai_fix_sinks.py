from __future__ import annotations

import dataclasses
import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from crackerjack.utils.xdg_paths import state_dir

from .ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    FixSessionFinished,
    FixSessionStarted,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PhaseChanged,
    PreflightFinished,
    PreflightStarted,
    RunFinished,
    RunStarted,
    TierTransitioned,
)

logger = logging.getLogger(__name__)

_EVENT_CLASSES: tuple[type[AIFixEvent], ...] = (
    RunStarted,
    IterationStarted,
    AgentDispatched,
    IssueResolved,
    IssueFailed,
    IterationFinished,
    RunFinished,
    PhaseChanged,
    PreflightStarted,
    PreflightFinished,
    FixSessionStarted,
    TierTransitioned,
    FixSessionFinished,
)


def runs_root(base_dir: Path | None = None) -> Path:
    """Where the AI-fix run history lives.

    ``$XDG_STATE_HOME/crackerjack/runs`` by default. The run history is
    append-only and grows without bound, so it is state, not a cache -
    and it must not live in the project tree, where ``git clean -fd``
    destroys it.

    Args:
        base_dir: A project root to keep the history beside instead.
            An explicit value wins, so a caller that wants the run
            directory somewhere specific keeps getting it.

    Returns:
        The directory that holds ``<run_id>/`` directories.
    """
    if base_dir is not None:
        return base_dir / ".crackerjack" / "runs"
    return state_dir("crackerjack") / "runs"


class JsonlSink:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir
        self._file: IO[str] | None = None
        self._run_dir: Path | None = None

    async def handle(self, event: AIFixEvent) -> None:
        if isinstance(event, RunStarted):
            self._open(event.run_id)
        if self._file is None:
            return
        try:
            payload = dataclasses.asdict(event)
            kind = getattr(type(event), "kind", None)
            if isinstance(kind, str):
                payload["kind"] = kind
            line = json.dumps(payload, default=str)
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as exc:
            logger.warning("JsonlSink dropped event after write error: %s", exc)
            self._file = None

    def _open(self, run_id: str) -> None:
        run_dir = runs_root(self._base_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._file = (run_dir / "events.jsonl").open("a", encoding="utf-8")
        self._run_dir = run_dir

        (run_dir / ".open").write_text(str(time.time()))

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        if self._run_dir is not None:
            sidecar = self._run_dir / ".open"
            if sidecar.exists():
                sidecar.unlink()
            self._run_dir = None

    @classmethod
    def restore_run(
        cls,
        run_id: str,
        base_dir: Path | None = None,
    ) -> Iterator[AIFixEvent]:
        root = runs_root(base_dir) / run_id
        jsonl_path = root / "events.jsonl"
        if not jsonl_path.exists():
            return
        kind_to_cls = {event_cls.kind: event_cls for event_cls in _EVENT_CLASSES}
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            kind = data.pop("kind", None)
            event_cls = kind_to_cls.get(kind) if isinstance(kind, str) else None
            if event_cls is None:
                continue
            valid_fields = {f.name for f in dataclasses.fields(event_cls)}
            yield event_cls(**{k: v for k, v in data.items() if k in valid_fields})


def detect_orphan_sidecars(base_dir: Path | None = None) -> list[str]:
    root = runs_root(base_dir)
    if not root.exists():
        return []
    orphans: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        sidecar = child / ".open"
        events = child / "events.jsonl"
        if sidecar.exists() and events.exists():
            orphans.append(child.name)
    return orphans

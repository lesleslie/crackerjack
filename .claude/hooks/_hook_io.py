"""Shared I/O helpers for Claude Code hook scripts in this project.

Centralizes:
- Reading the hook stdin JSON payload
- Extracting the session_id and cwd fields used by the worktree
  isolation hook

Used by:
- ``.claude/hooks/worktree-session-isolation.py`` (SessionStart hook)
- ``.claude/hooks/bodai-activity-subscriber.py`` (reference pattern)

The hook's stdin schema is documented in Claude Code's hook contract;
the relevant fields are:
- ``session_id`` (str | None) — Claude Code session UUID
- ``cwd`` (str | None) — current working directory of the session
- ``tool_name`` (str | None) — for PostToolUse hooks
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import sys
from typing import Any


@dataclass(frozen=True)
class HookPayload:
    """The fields we care about from a Claude Code hook stdin payload.

    Other fields may be present in the JSON but are ignored.
    """

    session_id: str
    cwd: str
    raw: dict[str, Any]


def _coerce_str(value: object) -> str:
    """Return ``value`` if it's a string, else empty string.

    Defends downstream code paths that pass these values to
    ``subprocess.run`` (which would ``TypeError`` on non-strings)
    or to ``Path(...)`` (which would accept them but produce
    surprising paths). Fail-closed: anything that isn't a plain
    ``str`` becomes ``""`` so the hook can take its empty-cwd /
    empty-session_id fast path.
    """
    return value if isinstance(value, str) else ""


def read_session_payload() -> HookPayload:
    """Read and parse the hook stdin JSON payload.

    Tolerates missing or non-JSON input by returning empty defaults
    rather than raising — hooks must never block Claude startup on a
    malformed payload (per the exit-0-always contract).

    Both ``session_id`` and ``cwd`` are type-validated as ``str``;
    any other JSON type (``int``, ``list``, ``dict``, ``bool``,
    ``float``, ``None``) is normalized to empty string. This is the
    fail-closed contract for the hook — malformed payloads must not
    reach ``subprocess.run`` and trigger a TypeError that violates
    the never-raises contract.
    """
    try:
        raw_str = sys.stdin.read()
    except OSError:
        return HookPayload(session_id="", cwd="", raw={})

    if not raw_str.strip():
        return HookPayload(session_id="", cwd="", raw={})

    try:
        raw = json.loads(raw_str)
    except json.JSONDecodeError:
        return HookPayload(session_id="", cwd="", raw={})

    if not isinstance(raw, dict):
        return HookPayload(session_id="", cwd="", raw={})

    session_id = _coerce_str(raw.get("session_id"))
    cwd = _coerce_str(raw.get("cwd"))
    return HookPayload(session_id=session_id, cwd=cwd, raw=raw)


__all__ = ["HookPayload", "read_session_payload"]

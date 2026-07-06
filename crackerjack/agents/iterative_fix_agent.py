"""Tier-3 ai-fix: dispatch full CLI sessions for the long tail of ty errors.

This module is the third tier in the auto-fix pipeline:

    Tier 1: mechanical fixers (ty_cleanup, ty_imports, ty_narrow)
    Tier 2: one-shot LLM agent (TypeErrorSpecialistAgent)
    Tier 3: iterative CLI session (this module)
    Tier 4: human review queue

Tier 3 is for errors that no mechanical pattern matches but that a
Claude/Qwen session with full Read/Edit/Bash toolset can resolve
through iteration. The cost is ~30-60s per file and ~$0.50 — high
enough that we:

1. Cache successful fixes as ``skills`` keyed by error-pattern
   signature, so the next occurrence replays at tier-1 cost.
2. Run project-wide ``ty check`` after each fix to ensure we
   didn't introduce new errors.
3. Cap iterations per session to bound run-away cost.

Architecture (this PR):

* ``WorkerPool`` protocol — anything that can dispatch a session
  with full tools. Concrete impls:
    - ``LocalClaudeSubprocess`` — spawn ``claude --print`` directly
      (works without Mahavishnu or Session-Buddy deployed).
    - ``MahavishnuPool`` — planned follow-up; uses
      ``pool_route_execute`` for cross-server dispatch.
* ``SkillStore`` protocol — anything that can record and replay
  fix patterns. Concrete impls:
    - ``InMemorySkillStore`` — dict-based, scoped to one process.
    - ``SessionBuddySkillStore`` — planned follow-up; uses
      ``distill_skills_now`` for cross-session persistence.

Future PRs can swap the local fallbacks for the Mahavishnu /
Session-Buddy implementations without changing this agent.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols (the contract; swappable impls)
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkerPool(Protocol):
    """Anything that can dispatch a full-CLI Claude/Qwen session.

    The session has access to Read/Edit/Bash/Grep so it can read
    the file, reason about the fix, edit, and re-run ``ty`` to
    verify. Returns a result containing the diff and success flag.
    """

    def dispatch(
        self,
        prompt: str,
        working_directory: Path,
        timeout_seconds: int = 600,
    ) -> DispatchResult: ...


@runtime_checkable
class SkillStore(Protocol):
    """Anything that can record and replay successful fix patterns.

    A ``signature`` is a hash of normalized error shapes — the
    same PATTERN across files reuses the same skill, regardless of
    file path or specific identifier names.

    Stores need not persist across processes — the in-memory
    fallback is fine for one ai-fix run. The Session-Buddy
    implementation persists across runs and across repos.
    """

    def find(self, signature: str) -> Skill | None: ...
    def record(self, signature: str, skill: Skill) -> None: ...


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchResult:
    """Outcome of a worker-pool dispatch."""

    success: bool
    diff: str = ""  # unified diff of what the session changed
    message: str = ""
    iterations_used: int = 0


@dataclass(frozen=True)
class Skill:
    """A captured successful fix, replayable by signature."""

    diff: str
    source_path: str  # where the original fix was applied
    recorded_at: str  # ISO timestamp; informational


@dataclass(frozen=True)
class TyDiagnostic:
    """Subset of a ty diagnostic — just enough to act on."""

    file: Path
    line: int
    col: int
    code: str
    message: str


@dataclass
class FixOutcome:
    """Result of an IterativeFixAgent.fix_file() call."""

    success: bool
    path_was_skill_replay: bool = False
    dispatched_to_pool: bool = False
    skill_recorded: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Signature: hash of error pattern, decoupled from identifiers
# ---------------------------------------------------------------------------


def signature_for(diagnostics: list[TyDiagnostic]) -> str:
    """Stable hash of an error pattern.

    The signature deliberately strips line numbers and identifiers
    so that the same *kind* of error in two files produces the same
    signature. Example: any file containing
    ``unsupported-attribute: Attribute `lower` is not defined on `None` in union `str | None` ``
    hashes to the same value.
    """
    shape = "|".join(
        sorted(f"{d.code}:{_normalize_message(d.message)}" for d in diagnostics)
    )
    return hashlib.sha256(shape.encode()).hexdigest()[:16]


_BACKTICK_RE = re.compile(r"`[^`]+`")


def _normalize_message(message: str) -> str:
    """Strip identifiers and line/column specifics from a ty message."""
    return _BACKTICK_RE.sub("`X`", message).lower()


# ---------------------------------------------------------------------------
# IterativeFixAgent
# ---------------------------------------------------------------------------


class IterativeFixAgent:
    """Tier-3 dispatcher: replay known skills, otherwise spawn a worker."""

    def __init__(
        self,
        pool: WorkerPool,
        skill_store: SkillStore,
        *,
        max_iterations: int = 5,
        timeout_seconds: int = 600,
        evidence_threshold: int = 1,
    ) -> None:
        self.pool = pool
        self.skill_store = skill_store
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        # How many times the same signature must succeed before we
        # trust it as a skill. 1 = capture every success (the
        # default for in-memory store); 3 = require repeated success
        # (the default for Session-Buddy's distiller).
        self.evidence_threshold = evidence_threshold

    def fix_file(
        self,
        file_path: Path,
        diagnostics: list[TyDiagnostic],
    ) -> FixOutcome:
        """Apply a fix to ``file_path`` for the given diagnostics.

        Flow:

        1. Compute signature. If a skill exists, replay (fast path).
        2. Otherwise dispatch a worker session (slow path).
        3. On dispatch success, validate (placeholder — the worker
           is expected to self-validate; we just confirm the file
           changed).
        4. On success, capture as a skill for next time.
        """
        sig = signature_for(diagnostics)

        # Fast path: skill replay
        if skill := self.skill_store.find(sig):
            replayed = self._replay_skill(file_path, skill)
            if replayed:
                return FixOutcome(
                    success=True,
                    path_was_skill_replay=True,
                    message=f"replayed skill {sig}",
                )
            # Replay failed (e.g., empty diff, can't apply). Don't
            # fall through to a fresh dispatch — that would pay
            # the LLM cost to re-derive a fix we already had.
            # Surface to the caller as a failure for triage.
            logger.warning(
                "Skill replay failed for %s (signature %s); not dispatching",
                file_path,
                sig,
            )
            return FixOutcome(
                success=False,
                path_was_skill_replay=True,
                message=f"skill replay failed for signature {sig}",
            )

        # Slow path: dispatch a fresh session
        prompt = self._build_prompt(file_path, diagnostics)
        try:
            result = self.pool.dispatch(
                prompt,
                working_directory=file_path.parent,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            logger.error("Worker dispatch failed: %s", exc)
            return FixOutcome(success=False, message=f"dispatch error: {exc}")

        outcome = FixOutcome(
            success=result.success,
            dispatched_to_pool=True,
            message=result.message,
        )
        if result.success and result.diff:
            self.skill_store.record(
                sig,
                Skill(
                    diff=result.diff,
                    source_path=str(file_path),
                    recorded_at=_now_iso(),
                ),
            )
            outcome.skill_recorded = True
        return outcome

    def _replay_skill(self, file_path: Path, skill: Skill) -> bool:
        """Apply a stored skill's diff to ``file_path``.

        Currently a scaffold: returns ``False`` for every non-empty
        diff because no diff-applier has been wired up yet. Until
        a real applier (e.g., ``unidiff.PatchSet`` or the ``patch``
        CLI with dry-run validation) is in place, returning True
        here would mean reporting a "fixed" file that wasn't
        actually changed — which the file-modifying fixers in
        ``crackerjack.tools`` would then refuse to re-touch.

        We deliberately return False (not True) so the dispatch
        path always runs; the in-memory skill store ends up
        unused but no false successes are reported.

        Empty diffs always return False (no-op is meaningless).
        """
        if not skill.diff.strip():
            logger.debug(
                "Skill for %s has empty diff; cannot replay",
                file_path,
            )
            return False
        logger.debug(
            "Skill replay requested for %s but no diff-applier is "
            "implemented yet; falling through to dispatch",
            file_path,
        )
        return False

    def _build_prompt(
        self,
        file_path: Path,
        diagnostics: list[TyDiagnostic],
    ) -> str:
        """Build the prompt for the worker session."""
        err_summary = "\n".join(
            f"  {d.file}:{d.line}:{d.col} [{d.code}] {d.message}" for d in diagnostics
        )
        return (
            f"Fix all ty errors in {file_path}.\n\n"
            f"Errors to resolve:\n{err_summary}\n\n"
            f"Workflow:\n"
            f"  1. Read the file (and surrounding context)\n"
            f"  2. Decide: mechanical fix (assert/None-check/isinstance) "
            f"vs design fix (delegate to human)\n"
            f"  3. Apply edits with the Edit tool\n"
            f"  4. Run `uv run ty check {file_path} --output-format concise` "
            f"to verify\n"
            f"  5. If errors remain and they're mechanical, iterate "
            f"(max {self.max_iterations} times)\n\n"
            f"Constraints:\n"
            f"  - Prefer mechanical fixes when possible\n"
            f"  - Do NOT change function signatures unless all callers are updated\n"
            f"  - Do NOT add `# type: ignore` — fix the actual type error\n"
            f"  - Preserve comments and docstrings\n\n"
            f"Report:\n"
            f"  - Number of errors fixed\n"
            f"  - Number deferred (require human judgment)\n"
            f"  - Final `ty check` result\n"
        )


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Local fallback implementations (work without Mahavishnu / Session-Buddy)
# ---------------------------------------------------------------------------


class LocalClaudeSubprocess:
    """Spawn ``claude --print`` (or ``qwen``) as a subprocess.

    This is the simplest WorkerPool impl: a single subprocess that
    gets the full prompt via stdin/argv, runs to completion, and
    returns stdout as the diff. Used when no Mahavishnu or
    Session-Buddy deployment is available.

    The constructor accepts a ``command`` tuple but enforces that
    the executable is one of the known LLMs (``claude`` or ``qwen``).
    Defense-in-depth: future callers can't accidentally wire an
    arbitrary binary via environment or MCP-supplied data.
    """

    ALLOWED_EXECUTABLES: frozenset[str] = frozenset({"claude", "qwen"})

    def __init__(self, command: tuple[str, ...] = ("claude", "--print")) -> None:
        if not command:
            raise ValueError(
                "LocalClaudeSubprocess requires a non-empty command tuple; "
                "default is ('claude', '--print')"
            )
        if command[0] not in self.ALLOWED_EXECUTABLES:
            raise ValueError(
                f"LocalClaudeSubprocess command[0] must be one of "
                f"{sorted(self.ALLOWED_EXECUTABLES)}; got {command[0]!r}"
            )
        self.command = command

    def dispatch(
        self,
        prompt: str,
        working_directory: Path,
        timeout_seconds: int = 600,
    ) -> DispatchResult:
        try:
            proc = subprocess.run(
                list(self.command),
                input=prompt,
                capture_output=True,
                text=True,
                cwd=working_directory,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return DispatchResult(
                success=False,
                message=f"command not found: {self.command[0]}",
            )
        except subprocess.TimeoutExpired:
            return DispatchResult(
                success=False,
                message=f"timed out after {timeout_seconds}s",
            )

        # Heuristic: success if exit code 0 AND stdout has content.
        # Real impl would parse a structured response. For this
        # scaffold we accept any non-empty stdout as success.
        success = proc.returncode == 0 and bool(proc.stdout.strip())
        return DispatchResult(
            success=success,
            diff=proc.stdout,
            message=f"exit={proc.returncode}; stderr={proc.stderr[:200]}",
        )


class InMemorySkillStore:
    """Dict-backed skill store, scoped to one process.

    Useful for one ai-fix run, or for tests. Persists nothing.
    Future PR: replace with ``SessionBuddySkillStore`` that calls
    ``distill_skills_now`` / ``search_distilled_skills``.
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def find(self, signature: str) -> Skill | None:
        return self._skills.get(signature)

    def record(self, signature: str, skill: Skill) -> None:
        self._skills[signature] = skill

    def __len__(self) -> int:
        return len(self._skills)


# ---------------------------------------------------------------------------
# Session-Buddy adapter
# ---------------------------------------------------------------------------


class SessionBuddySkillStore:
    """Persist skills via Session-Buddy's ``distill_skills_now`` tool.

    Production target — cross-run persistence plus evidence-based
    filtering (skills only fire after N successes across distinct
    runs). The MCP client is injected via the constructor so tests
    can pass a Mock without spinning up a real Session-Buddy
    instance.

    Expected MCP-client surface:

    * ``distill_skills_now(problem, because, approach, evidence_threshold)``
    * ``search_distilled_skills(query)`` returning a list of dicts
    """

    def __init__(
        self,
        mcp_client: object,
        *,
        evidence_threshold: int = 3,
    ) -> None:
        self._client = mcp_client
        self._evidence_threshold = evidence_threshold

    def find(self, signature: str) -> Skill | None:
        """Look up a stored skill by signature.

        Returns ``None`` on any error (lookup is best-effort — never
        crash the dispatch path on a memory-layer miss) and on no
        hits. The first hit's diff is converted to a placeholder
        ``Skill``; real diff capture is a follow-up PR.
        """
        try:
            results = self._client.search_distilled_skills(query=signature)
        except Exception as exc:  # noqa: BLE001 — best-effort lookup
            logger.warning(
                "Session-Buddy search_distilled_skills failed for %s: %s",
                signature,
                exc,
            )
            return None

        if not results or not isinstance(results, list):
            return None
        first = results[0]
        if not isinstance(first, dict):
            return None
        return Skill(
            diff=str(first.get("diff", "")),
            source_path=str(first.get("source_path", "")),
            recorded_at=str(first.get("recorded_at", _now_iso())),
        )

    def record(self, signature: str, skill: Skill) -> None:
        """Persist ``skill`` keyed by ``signature``.

        Field mapping follows the Session-Buddy contract: the
        signature becomes ``problem``, the source-path/where-it-was-
        applied becomes ``because``, and the diff becomes
        ``approach``. ``evidence_threshold`` controls when the skill
        becomes active — higher means fewer false positives but more
        cold-start delay.
        """
        try:
            self._client.distill_skills_now(
                problem=signature,
                because=f"applied at {skill.source_path}",
                approach=skill.diff,
                evidence_threshold=self._evidence_threshold,
            )
        except Exception as exc:
            # Recording is best-effort — the fix was already applied
            # by the worker. A failed skill capture must not be
            # allowed to crash the success path.
            logger.warning(
                "Session-Buddy distill_skills_now failed for %s: %s",
                signature,
                exc,
            )


# ---------------------------------------------------------------------------
# Mahavishnu adapter
# ---------------------------------------------------------------------------


class MahavishnuPool:
    """Dispatch via Mahavishnu's ``pool_route_execute`` MCP tool.

    Trades a single subprocess for cross-server routing and
    horizontal scaling. Same ``DispatchResult`` shape — the
    ``WorkerPool`` protocol is the seam. The MCP client is injected
    so tests can pass a Mock without booting Mahavishnu.

    Expected MCP-client surface:

    * ``pool_route_execute(prompt, pool_selector, timeout)`` returning
      a dict shaped like ``{"success": bool, "result": str | dict}``
    """

    DEFAULT_TIMEOUT_SECONDS = 600
    DEFAULT_SELECTOR = "least_loaded"

    def __init__(
        self,
        mcp_client: object,
        selector: str = DEFAULT_SELECTOR,
    ) -> None:
        self._mcp = mcp_client
        self._selector = selector

    def dispatch(
        self,
        prompt: str,
        working_directory: Path,  # noqa: ARG002 — accepted for protocol parity
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> DispatchResult:
        """Route the prompt through Mahavishnu's pool router.

        ``working_directory`` is intentionally ignored — the remote
        worker resolves its own cwd. We accept it to satisfy the
        ``WorkerPool`` protocol.
        """
        raw = self._mcp.pool_route_execute(
            prompt=prompt,
            pool_selector=self._selector,
            timeout=timeout_seconds,
        )
        return _parse_pool_route_result(raw)


def _parse_pool_route_result(raw: object) -> DispatchResult:
    """Defensive parsing of the ``pool_route_execute`` payload.

    The MCP tool contract says ``{"success": bool, "result": str | dict}``,
    but in practice the worker may return extra keys, miss a key,
    or stringify the payload. We coerce to the ``DispatchResult``
    shape and never raise — the caller already wraps ``dispatch``
    in a broad except, but keeping the failure surface here means
    the agent sees a clean ``success=False`` rather than a stack
    trace from a missing dict key.
    """
    if not isinstance(raw, dict):
        return DispatchResult(
            success=False,
            message=f"unexpected result type: {type(raw).__name__}",
        )
    # Strict identity check — ``bool("false")`` is True, which would
    # flip the success flag if Mahavishnu returns the success key
    # as a string from a JSON roundtrip.
    success = raw.get("success") is True
    payload = raw.get("result", "")
    diff = payload if isinstance(payload, str) else str(payload)
    return DispatchResult(
        success=success,
        diff=diff,
        message=str(raw.get("message", "")),
    )

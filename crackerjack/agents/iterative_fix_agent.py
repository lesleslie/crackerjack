from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Protocol, runtime_checkable

from unidiff import PatchSet
from unidiff.errors import UnidiffParseError

logger = logging.getLogger(__name__)


_MAX_DIFF_BYTES = 1 * 1024 * 1024


@runtime_checkable
class WorkerPool(Protocol):
    def dispatch(
        self,
        prompt: str,
        working_directory: Path,
        timeout_seconds: int = 600,
    ) -> DispatchResult: ...


@runtime_checkable
class SkillStore(Protocol):
    def find(self, signature: str) -> Skill | None: ...
    def record(self, signature: str, skill: Skill) -> None: ...


@dataclass(frozen=True)
class DispatchResult:
    success: bool
    diff: str = ""
    message: str = ""
    iterations_used: int = 0


@dataclass(frozen=True)
class Skill:
    diff: str
    source_path: str
    recorded_at: str


@dataclass(frozen=True)
class TyDiagnostic:
    file: Path
    line: int
    col: int
    code: str
    message: str


@dataclass
class FixOutcome:
    success: bool
    path_was_skill_replay: bool = False
    dispatched_to_pool: bool = False
    skill_recorded: bool = False
    message: str = ""


def signature_for(diagnostics: list[TyDiagnostic]) -> str:
    shape = "|".join(sorted(signature_shape(d.code, d.message) for d in diagnostics))
    return hashlib.sha256(shape.encode()).hexdigest()[:16]


def signature_shape(code: str, message: str) -> str:
    return f"{code}:{_normalize_message(message)}"


_BACKTICK_RE = re.compile(r"`[^`]+`")


def _normalize_message(message: str) -> str:
    return _BACKTICK_RE.sub("`X`", message).lower()


class IterativeFixAgent:
    def __init__(
        self,
        pool: WorkerPool,
        skill_store: SkillStore | None = None,
        *,
        max_iterations: int = 5,
        timeout_seconds: int = 600,
        evidence_threshold: int = 1,
    ) -> None:
        self.pool = pool

        self.skill_store: SkillStore = (
            skill_store if skill_store is not None else InMemorySkillStore()
        )
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds

        self.evidence_threshold = evidence_threshold

        self._success_counts: dict[str, int] = {}

        self.last_generated_skill: Skill | None = None

    def fix_file(
        self,
        file_path: Path,
        diagnostics: list[TyDiagnostic],
    ) -> FixOutcome:
        sig = signature_for(diagnostics)

        if skill := self.skill_store.find(sig):
            replayed = self._replay_skill(file_path, skill)
            if replayed:
                return FixOutcome(
                    success=True,
                    path_was_skill_replay=True,
                    message=f"replayed skill {sig}",
                )

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
            self._success_counts[sig] = self._success_counts.get(sig, 0) + 1
            if self._success_counts[sig] >= self.evidence_threshold:
                recorded_skill = Skill(
                    diff=result.diff,
                    source_path=str(file_path),
                    recorded_at=_now_iso(),
                )
                self.skill_store.record(sig, recorded_skill)

                self.last_generated_skill = recorded_skill
                outcome.skill_recorded = True
        return outcome

    def _replay_skill(self, file_path: Path, skill: Skill) -> bool:
        if not skill.diff.strip():
            logger.debug(
                "Skill for %s has empty diff; cannot replay",
                file_path,
            )
            return False

        if len(skill.diff.encode("utf-8")) > _MAX_DIFF_BYTES:
            logger.warning(
                "Skill diff for %s exceeds %d bytes; refusing to parse",
                file_path,
                _MAX_DIFF_BYTES,
            )
            return False

        try:
            patch = PatchSet.from_string(skill.diff)
        except UnidiffParseError as exc:
            logger.warning(
                "Skill diff for %s is malformed: %s",
                file_path,
                exc,
            )
            return False
        except Exception as exc:  # noqa: BLE001 — defensive: any parser bug
            logger.warning(
                "Skill diff for %s failed to parse: %s: %s",
                file_path,
                type(exc).__name__,
                exc,
            )
            return False

        if not patch:
            logger.warning(
                "Skill diff for %s parsed to empty patch set",
                file_path,
            )
            return False

        if not file_path.exists():
            logger.warning(
                "Cannot replay skill for %s: file does not exist",
                file_path,
            )
            return False

        patched_file = _match_patch_file(patch, file_path)
        if patched_file is None:
            logger.warning(
                "Skill diff targets a different file: expected %s, patch contains %s",
                file_path,
                [pf.path for pf in patch],
            )
            return False

        original = file_path.read_text()
        new_content = _apply_patch(original, patched_file, file_path)
        if new_content is None:
            return False

        import os
        import tempfile

        fd, tmp_path = tempfile.mkstemp(
            prefix=f".{file_path.name}.",
            suffix=".replay.tmp",
            dir=str(file_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            os.replace(tmp_path, file_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return True

    def _build_prompt(
        self,
        file_path: Path,
        diagnostics: list[TyDiagnostic],
    ) -> str:
        err_summary = "\n".join(
            f" {d.file}:{d.line}:{d.col} [{d.code}] {d.message}" for d in diagnostics
        )
        return (
            f"Fix all ty errors in {file_path}.\n\n"
            f"Errors to resolve:\n{err_summary}\n\n"
            f"Workflow:\n"
            f" 1. Read the file (and surrounding context)\n"
            f" 2. Decide: mechanical fix (assert/None-check/isinstance) "
            f"vs design fix (delegate to human)\n"
            f" 3. Apply edits with the Edit tool\n"
            f" 4. Run `uv run ty check {file_path} --output-format concise` "
            f"to verify\n"
            f" 5. If errors remain and they're mechanical, iterate "
            f"(max {self.max_iterations} times)\n\n"
            f"Constraints:\n"
            f" - Prefer mechanical fixes when possible\n"
            f" - Do NOT change function signatures unless all callers are updated\n"
            f" - Do NOT add `# type: ignore` — fix the actual type error\n"
            f" - Preserve comments and docstrings\n\n"
            f"Report:\n"
            f" - Number of errors fixed\n"
            f" - Number deferred (require human judgment)\n"
            f" - Final `ty check` result\n"
        )


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


def _match_patch_file(patch: PatchSet, file_path: Path) -> object | None:
    target = file_path.resolve(strict=False)
    for patched_file in patch:
        try:
            candidate_path = Path(patched_file.path)
            if not candidate_path.is_absolute():
                candidate = (file_path.parent / candidate_path).resolve(strict=False)
            else:
                candidate = candidate_path.resolve(strict=False)
        except (OSError, ValueError):
            continue
        if candidate == target:
            return patched_file
    return None


def _apply_patch(
    original: str,
    patched_file: object,
    file_path: Path,
) -> str | None:
    lines = original.splitlines(keepends=True)

    sorted_hunks = sorted(patched_file, key=lambda h: -h.source_start)

    for hunk in sorted_hunks:
        if hunk.source_start == 0:
            start_idx = 0
            expected: list[str] = []
            actual = lines[start_idx : start_idx + hunk.source_length]
            if actual != expected:
                logger.warning(
                    "Hunk insertion at line 0 in %s did not match "
                    "expected empty context",
                    file_path,
                )
                return None
        else:
            start_idx = hunk.source_start - 1
            expected = [line.value for line in hunk.source_lines()]
            actual = lines[start_idx : start_idx + hunk.source_length]
            if actual != expected:
                logger.warning(
                    "Hunk context mismatch in %s at line %d: expected %r, got %r",
                    file_path,
                    hunk.source_start,
                    expected,
                    actual,
                )
                return None

        target_lines = [line.value for line in hunk.target_lines()]
        lines[start_idx : start_idx + hunk.source_length] = target_lines

    return "".join(lines)


class LocalClaudeSubprocess:
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

        success = proc.returncode == 0 and bool(proc.stdout.strip())
        return DispatchResult(
            success=success,
            diff=proc.stdout,
            message=f"exit={proc.returncode}; stderr={proc.stderr[:200]}",
        )


class InMemorySkillStore:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def find(self, signature: str) -> Skill | None:
        return self._skills.get(signature)

    def record(self, signature: str, skill: Skill) -> None:
        self._skills[signature] = skill

    def __len__(self) -> int:
        return len(self._skills)


class SessionBuddySkillStore:
    def __init__(
        self,
        mcp_client: object,
        *,
        evidence_threshold: int = 3,
    ) -> None:
        self._client = mcp_client
        self._evidence_threshold = evidence_threshold

    def find(self, signature: str) -> Skill | None:
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
        try:
            self._client.distill_skills_now(
                problem=signature,
                because=f"applied at {skill.source_path}",
                approach=skill.diff,
                evidence_threshold=self._evidence_threshold,
            )
        except Exception as exc:
            logger.warning(
                "Session-Buddy distill_skills_now failed for %s: %s",
                signature,
                exc,
            )


class MahavishnuPool:
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
        raw = self._mcp.pool_route_execute(
            prompt=prompt,
            pool_selector=self._selector,
            timeout=timeout_seconds,
        )
        return _parse_pool_route_result(raw)


def _parse_pool_route_result(raw: object) -> DispatchResult:
    if not isinstance(raw, dict):
        return DispatchResult(
            success=False,
            message=f"unexpected result type: {type(raw).__name__}",
        )

    success = raw.get("success") is True
    payload = raw.get("result", "")
    diff = payload if isinstance(payload, str) else str(payload)
    return DispatchResult(
        success=success,
        diff=diff,
        message=str(raw.get("message", "")),
    )

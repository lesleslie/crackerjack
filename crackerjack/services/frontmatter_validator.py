from __future__ import annotations

import dataclasses
import json
import logging
import subprocess
import sys
import typing as t
from pathlib import Path

from crackerjack.services import secure_subprocess as _secure_subprocess

logger = logging.getLogger(__name__)


class _SecureSubprocessAdapter:
    """Expose the subprocess API expected by this service.

    Crackerjack's secure subprocess module exposes
    ``execute_secure_subprocess`` rather than a module-level ``run`` helper.
    Keeping the adapter local preserves the service's patchable ``run`` seam
    without changing the shared subprocess module.
    """

    @staticmethod
    def run(command: list[str], **kwargs: t.Any) -> subprocess.CompletedProcess[str]:
        return _secure_subprocess.execute_secure_subprocess(command, **kwargs)


secure_subprocess = _SecureSubprocessAdapter()


@dataclasses.dataclass
class FrontmatterValidationIssue:
    file: str
    line: int
    code: str
    message: str

    def __getitem__(self, key: str) -> str | int:
        """Support the mapping-style access used by legacy callers."""
        if key not in {"file", "line", "code", "message"}:
            raise KeyError(key)
        return getattr(self, key)


@dataclasses.dataclass
class FrontmatterValidationResult:
    success: bool
    files_scanned: int
    errors: list[FrontmatterValidationIssue]
    warnings: list[FrontmatterValidationIssue]
    duration_ms: int
    error_count: int = 0
    warning_count: int = 0

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, t.Any] | list[t.Any],
        exit_success: bool,
    ) -> FrontmatterValidationResult:
        if isinstance(payload, list):
            return cls._from_file_results(payload, exit_success)

        errors = [cls._issue_from_payload(issue) for issue in payload.get("errors", [])]
        warnings = [
            cls._issue_from_payload(issue) for issue in payload.get("warnings", [])
        ]
        return cls(
            success=exit_success and not errors,
            files_scanned=int(payload.get("files_scanned", 0)),
            errors=errors,
            warnings=warnings,
            duration_ms=int(payload.get("duration_ms", 0)),
            error_count=len(errors),
            warning_count=len(warnings),
        )

    @classmethod
    def _from_file_results(
        cls,
        payload: list[t.Any],
        exit_success: bool,
    ) -> FrontmatterValidationResult:
        errors: list[FrontmatterValidationIssue] = []
        warnings: list[FrontmatterValidationIssue] = []
        for file_result in payload:
            if not isinstance(file_result, dict):
                continue
            path = str(file_result.get("path", ""))
            errors.extend(
                cls._issue_from_payload(issue, path=path)
                for issue in file_result.get("errors", [])
            )
            warnings.extend(
                cls._issue_from_payload(issue, path=path)
                for issue in file_result.get("warnings", [])
            )
        return cls(
            success=exit_success and not errors,
            files_scanned=len(payload),
            errors=errors,
            warnings=warnings,
            duration_ms=0,
            error_count=len(errors),
            warning_count=len(warnings),
        )

    @staticmethod
    def _issue_from_payload(
        issue: t.Any,
        *,
        path: str = "",
    ) -> FrontmatterValidationIssue:
        if not isinstance(issue, dict):
            return FrontmatterValidationIssue(
                file=path,
                line=0,
                code="unknown",
                message=str(issue),
            )
        return FrontmatterValidationIssue(
            file=str(issue.get("file", path)),
            line=int(issue.get("line", 0)),
            code=str(issue.get("code", issue.get("rule", "unknown"))),
            message=str(issue.get("message", "")),
        )


class FrontmatterValidationError(Exception):
    def __init__(
        self,
        message: str,
        result: FrontmatterValidationResult | None = None,
        reason: str = "errors",
    ) -> None:
        super().__init__(message)
        self.result = result
        self.reason = reason


class FrontmatterValidator:
    DEFAULT_TIMEOUT = 120

    def __init__(
        self,
        pkg_path: Path | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.pkg_path = (pkg_path or Path.cwd()).resolve()
        self.timeout_seconds = timeout_seconds

    def _build_command(
        self,
        strict: bool,
        allow_nonstandard: bool,
        validate_links: bool,
        store: str | None,
    ) -> list[str]:
        cmd: list[str] = [
            sys.executable,
            "scripts/validate_document_frontmatter.py",
            "--json",
        ]
        if strict:
            cmd.append("--strict")
        if allow_nonstandard:
            cmd.append("--allow-nonstandard")
        if validate_links:
            cmd.append("--validate-links")
        if store:
            cmd.extend(["--store", store])
        return cmd

    def validate(
        self,
        strict: bool = False,
        allow_nonstandard: bool = True,
        validate_links: bool = False,
        store: str | None = None,
    ) -> FrontmatterValidationResult:
        cmd = self._build_command(strict, allow_nonstandard, validate_links, store)
        try:
            completed = secure_subprocess.run(
                cmd,
                cwd=str(self.pkg_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            raise FrontmatterValidationError(
                f"validator timed out after {self.timeout_seconds}s",
                reason="timeout",
            ) from exc
        except Exception as exc:
            raise FrontmatterValidationError(
                f"validator crashed: {exc}",
                reason="crash",
            ) from exc

        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise FrontmatterValidationError(
                f"validator returned invalid JSON: {exc}; stderr={completed.stderr!r}",
                reason="crash",
            ) from exc

        return FrontmatterValidationResult.from_payload(
            payload,
            exit_success=completed.returncode == 0,
        )

    def validate_or_raise(self, **kwargs: t.Any) -> FrontmatterValidationResult:
        result = self.validate(**kwargs)
        if not result.success:
            raise FrontmatterValidationError(
                f"{result.error_count} errors, {result.warning_count} warnings",
                result=result,
                reason="errors",
            )
        return result

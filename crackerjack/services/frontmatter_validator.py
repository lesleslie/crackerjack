from __future__ import annotations

import dataclasses
import typing as t
from pathlib import Path

from crackerjack.services import frontmatter as _validator


@dataclasses.dataclass
class FrontmatterValidationIssue:
    file: str
    line: int
    code: str
    message: str

    def __getitem__(self, key: str) -> str | int:
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

    def validate(
        self,
        strict: bool = False,
        allow_nonstandard: bool = True,
        validate_links: bool = False,
        store: str | None = None,
        skip_link_note: bool = True,
    ) -> FrontmatterValidationResult:
        try:
            stores = _resolve_stores(self.pkg_path, store)
            files = _validator.discover_files(self.pkg_path, stores, [])
        except Exception as exc:
            raise FrontmatterValidationError(
                f"validator crashed during file discovery: {exc}",
                reason="crash",
            ) from exc

        known_files = {rel for _, rel in files}
        known_topics = _validator.load_seed_topics(self.pkg_path)

        results: list[t.Any] = []
        for abs_path, rel in files:
            try:
                results.append(
                    _validator.validate_file(
                        abs_path,
                        rel,
                        repo_root=self.pkg_path,
                        known_files=known_files,
                        known_topics=known_topics,
                        strict=strict,
                        allow_nonstandard=allow_nonstandard,
                        validate_links=validate_links,
                        skip_link_note=skip_link_note,
                    )
                )
            except Exception as exc:
                raise FrontmatterValidationError(
                    f"validator crashed on {rel}: {exc}",
                    reason="crash",
                ) from exc

        return FrontmatterValidationResult.from_payload(
            [
                {
                    "path": r.path,
                    "status": r.status,
                    "errors": [
                        {"rule": i.rule, "message": i.message} for i in r.errors
                    ],
                    "warnings": [
                        {"rule": i.rule, "message": i.message} for i in r.warnings
                    ],
                }
                for r in results
            ],
            exit_success=True,
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


def _resolve_stores(
    pkg_path: Path,
    store: str | None,
) -> list[Path]:
    if store:
        rel = _validator.STORE_LOOKUP[store]
        return [pkg_path / rel]
    return [pkg_path / s for s in _validator.DEFAULT_STORES]

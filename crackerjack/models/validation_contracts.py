from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GateSeverity(StrEnum):
    REQUIRED = "required"
    WARNING = "warning"
    OPTIONAL = "optional"


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return dict(value.model_dump())
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return {key: val for key, val in vars(value).items() if not key.startswith("_")}
    return {}


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        with suppress(ValueError):
            return datetime.fromisoformat(value)
    return datetime.now(UTC)


def _coerce_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(item) for item in value.values()]
    return [str(item) for item in value]


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str
    file_path: str | None = None
    line_number: int | None = None
    code: str | None = None
    category: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> ValidationIssue:
        if isinstance(value, cls):
            return value

        data = _coerce_mapping(value)
        if not data and isinstance(value, str):
            data = {"message": value}

        severity = data.get("severity", ValidationSeverity.ERROR)
        try:
            severity = ValidationSeverity(str(severity))
        except ValueError:
            severity = ValidationSeverity.ERROR

        file_path = data.get("file_path")

        line_number = data.get("line_number")
        if line_number is not None:
            try:
                line_number = int(line_number)
            except (TypeError, ValueError):
                line_number = None

        details = data.get("details")
        if not isinstance(details, dict):
            details = {}

        return cls(
            severity=severity,
            message=str(data.get("message", data.get("error_message", ""))),
            file_path=file_path,
            line_number=line_number,
            code=data["code"] if data.get("code") is not None else None,
            category=data["category"] if data.get("category") is not None else None,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    valid: bool
    validation_type: str = ""
    source: str = "crackerjack"
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue for issue in self.issues if issue.severity == ValidationSeverity.ERROR
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == ValidationSeverity.WARNING
        ]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["error_count"] = self.error_count
        data["warning_count"] = self.warning_count
        return data

    @classmethod
    def from_result(
        cls,
        value: Any,
        validation_type: str = "",
        source: str = "crackerjack",
        metadata: dict[str, Any] | None = None,
    ) -> ValidationReport:
        data = _coerce_mapping(value)

        issues_source: list[Any] = data.get("issues") or data.get("errors") or []
        if isinstance(issues_source, str):
            issues_source = [issues_source]
        issues = [ValidationIssue.from_value(item) for item in issues_source]

        valid_value = data.get("valid", data.get("success", data.get("passed")))
        if valid_value is None:
            valid_value = not issues

        merged_metadata: dict[str, Any] = {}
        if metadata:
            merged_metadata.update(metadata)
        extra_metadata = data.get("metadata") or data.get("details")
        if isinstance(extra_metadata, dict):
            merged_metadata.update(extra_metadata)

        summary = str(data.get("summary", data.get("message", "")))
        if not summary and issues:
            summary = issues[0].message

        return cls(
            valid=bool(valid_value),
            validation_type=validation_type or str(data.get("validation_type", "")),
            source=source or str(data.get("source", "crackerjack")),
            issues=issues,
            summary=summary,
            generated_at=_coerce_datetime(data.get("generated_at")),
            metadata=merged_metadata,
        )


class QualityGateCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    passed: bool
    severity: GateSeverity = GateSeverity.REQUIRED
    score: float | None = None
    threshold: float | None = None
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None

    @classmethod
    def from_value(cls, value: Any) -> QualityGateCheck:
        if isinstance(value, cls):
            return value

        data = _coerce_mapping(value)
        severity = data.get("severity", GateSeverity.REQUIRED)
        try:
            severity = GateSeverity(str(severity))
        except ValueError:
            severity = GateSeverity.REQUIRED

        details = data.get("details")
        if not isinstance(details, dict):
            details = {}

        score = data.get("score")
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                score = None

        threshold = data.get("threshold")
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                threshold = None

        duration_ms = data.get("duration_ms")
        if duration_ms is not None:
            try:
                duration_ms = float(duration_ms)
            except (TypeError, ValueError):
                duration_ms = None

        return cls(
            name=str(data.get("name", "unknown")),
            passed=bool(data.get("passed", False)),
            severity=severity,
            score=score,
            threshold=threshold,
            message=str(data.get("message", "")),
            details=details,
            duration_ms=duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class QualityGateReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fast_hooks: bool
    tests: bool
    comprehensive: bool
    coverage: float
    errors: list[str] = Field(default_factory=list)
    checks: list[QualityGateCheck] = Field(default_factory=list)
    repository: str = ""
    profile: str = ""
    source: str = "crackerjack"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.fast_hooks and self.tests and self.comprehensive

    @property
    def all_passed(self) -> bool:
        return self.passed

    @property
    def blocking_failure(self) -> bool:
        return not self.fast_hooks or not self.tests

    @property
    def warnings(self) -> list[str]:
        return [
            check.name
            for check in self.checks
            if not check.passed and check.severity == GateSeverity.WARNING
        ]

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["passed"] = self.passed
        data["all_passed"] = self.all_passed
        data["blocking_failure"] = self.blocking_failure
        data["warnings"] = self.warnings
        return data

    @classmethod
    def from_result(
        cls,
        value: Any,
        repository: str = "",
        profile: str = "",
        source: str = "crackerjack",
        metadata: dict[str, Any] | None = None,
    ) -> QualityGateReport:
        data = _coerce_mapping(value)

        checks_source = data.get("checks") or []
        if isinstance(checks_source, str):
            checks_source = [checks_source]
        checks = [QualityGateCheck.from_value(item) for item in checks_source]

        fast_hooks = bool(data.get("fast_hooks", data.get("passed", False)))
        tests = bool(data.get("tests", data.get("tests_passed", fast_hooks)))
        comprehensive = bool(
            data.get("comprehensive", data.get("all_passed", fast_hooks and tests))
        )

        if not checks:
            checks = [
                QualityGateCheck(
                    name="fast_hooks",
                    passed=fast_hooks,
                    severity=GateSeverity.REQUIRED,
                ),
                QualityGateCheck(
                    name="tests",
                    passed=tests,
                    severity=GateSeverity.REQUIRED,
                ),
                QualityGateCheck(
                    name="comprehensive",
                    passed=comprehensive,
                    severity=GateSeverity.OPTIONAL,
                ),
            ]

        errors = _coerce_string_list(
            data.get("errors") or data.get("failed_required_checks")
        )
        if not errors:
            errors = [
                check.name
                for check in checks
                if not check.passed and check.severity == GateSeverity.REQUIRED
            ]

        merged_metadata: dict[str, Any] = {}
        if metadata:
            merged_metadata.update(metadata)
        extra_metadata = data.get("metadata")
        if isinstance(extra_metadata, dict):
            merged_metadata.update(extra_metadata)

        coverage_value = data.get("coverage", data.get("overall_score", 0.0))
        try:
            coverage = float(coverage_value)
        except (TypeError, ValueError):
            coverage = 0.0

        return cls(
            fast_hooks=fast_hooks,
            tests=tests,
            comprehensive=comprehensive,
            coverage=coverage,
            errors=errors,
            checks=checks,
            repository=repository or str(data.get("repository", "")),
            profile=profile or str(data.get("profile", "")),
            source=source or str(data.get("source", "crackerjack")),
            generated_at=_coerce_datetime(data.get("generated_at")),
            metadata=merged_metadata,
        )


__all__ = [
    "GateSeverity",
    "QualityGateCheck",
    "QualityGateReport",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]

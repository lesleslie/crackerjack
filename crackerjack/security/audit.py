import typing as t
from dataclasses import dataclass

from crackerjack.config.hooks import SecurityLevel


@dataclass
class SecurityCheckResult:
    hook_name: str
    security_level: SecurityLevel
    passed: bool
    error_message: str | None = None
    details: dict[str, t.Any] | None = None


@dataclass
class SecurityAuditReport:
    critical_failures: list[SecurityCheckResult]
    high_failures: list[SecurityCheckResult]
    medium_failures: list[SecurityCheckResult]
    low_failures: list[SecurityCheckResult]

    allows_publishing: bool
    security_warnings: list[str]
    recommendations: list[str]

    @property
    def has_critical_failures(self) -> bool:
        return len(self.critical_failures) > 0

    @property
    def total_failures(self) -> int:
        return (
            len(self.critical_failures)
            + len(self.high_failures)
            + len(self.medium_failures)
            + len(self.low_failures)
        )


class SecurityAuditor:
    CRITICAL_HOOKS = {
        "bandit": "Security vulnerability detection (OWASP A09)",
        "pyright": "Type safety prevents runtime security holes (OWASP A04)",
        "gitleaks": "Secret/credential detection (OWASP A07)",
    }

    HIGH_SECURITY_HOOKS = {
        "validate-regex-patterns": "Regex vulnerability detection",
        "creosote": "Dependency vulnerability analysis",
        "check-added-large-files": "Large file security analysis",
        "uv-lock": "Dependency lock security",
    }

    def audit_hook_results(
        self, fast_results: list[t.Any], comprehensive_results: list[t.Any]
    ) -> SecurityAuditReport:
        all_results = fast_results + comprehensive_results

        critical_failures = []
        high_failures = []
        medium_failures = []
        low_failures = []

        for result in all_results:
            check_result = self._analyze_hook_result(result)
            if not check_result.passed:
                if check_result.security_level == SecurityLevel.CRITICAL:
                    critical_failures.append(check_result)
                elif check_result.security_level == SecurityLevel.HIGH:
                    high_failures.append(check_result)
                elif check_result.security_level == SecurityLevel.MEDIUM:
                    medium_failures.append(check_result)
                else:
                    low_failures.append(check_result)

        allows_publishing = len(critical_failures) == 0

        security_warnings = self._generate_security_warnings(
            critical_failures, high_failures, medium_failures
        )

        recommendations = self._generate_security_recommendations(
            critical_failures, high_failures, medium_failures
        )

        return SecurityAuditReport(
            critical_failures=critical_failures,
            high_failures=high_failures,
            medium_failures=medium_failures,
            low_failures=low_failures,
            allows_publishing=allows_publishing,
            security_warnings=security_warnings,
            recommendations=recommendations,
        )

    def _analyze_hook_result(self, result: t.Any) -> SecurityCheckResult:
        hook_name = getattr(result, "name", "unknown")
        is_failed = getattr(result, "status", "unknown") in (
            "failed",
            "error",
            "timeout",
        )
        error_message = getattr(result, "output", None) or getattr(
            result, "error", None
        )

        security_level = self._get_hook_security_level(hook_name)

        return SecurityCheckResult(
            hook_name=hook_name,
            security_level=security_level,
            passed=not is_failed,
            error_message=error_message,
            details={"status": getattr(result, "status", "unknown")},
        )

    def _get_hook_security_level(self, hook_name: str) -> SecurityLevel:
        hook_name_lower = hook_name.lower()

        if hook_name_lower in (name.lower() for name in self.CRITICAL_HOOKS):
            return SecurityLevel.CRITICAL
        elif hook_name_lower in (name.lower() for name in self.HIGH_SECURITY_HOOKS):
            return SecurityLevel.HIGH
        elif hook_name_lower in ("ruff-check", "vulture", "refurb", "complexipy"):
            return SecurityLevel.MEDIUM
        return SecurityLevel.LOW

    def _generate_security_warnings(
        self,
        critical: list[SecurityCheckResult],
        high: list[SecurityCheckResult],
        medium: list[SecurityCheckResult],
    ) -> list[str]:
        warnings = []

        if critical:
            warnings.append(
                f"🔒 CRITICAL: {len(critical)} security-critical checks failed - publishing BLOCKED"
            )
            for failure in critical:
                reason = self.CRITICAL_HOOKS.get(
                    failure.hook_name.lower(), "Security-critical check"
                )
                warnings.append(f" • {failure.hook_name}: {reason}")

        if high:
            warnings.append(
                f"⚠️ HIGH: {len(high)} high-security checks failed - review recommended"
            )

        if medium:
            warnings.append(f"ℹ️ MEDIUM: {len(medium)} standard quality checks failed")

        return warnings

    def _generate_security_recommendations(
        self,
        critical: list[SecurityCheckResult],
        high: list[SecurityCheckResult],
        medium: list[SecurityCheckResult],
    ) -> list[str]:
        recommendations = []

        if critical:
            recommendations.append(
                "🔧 Fix all CRITICAL security issues before publishing"
            )

            critical_names = [f.hook_name.lower() for f in critical]

            if "bandit" in critical_names:
                recommendations.append(
                    " • Review bandit security findings - may indicate vulnerabilities"
                )
            if "pyright" in critical_names:
                recommendations.append(
                    " • Fix type errors - type safety prevents runtime security holes"
                )
            if "gitleaks" in critical_names:
                recommendations.append(
                    " • Remove secrets/credentials from code - use environment variables"
                )

        if high:
            recommendations.append(
                "🔍 Review HIGH-security findings before production deployment"
            )

        if not critical and not high:
            recommendations.append("✅ Security posture is acceptable for publishing")

        recommendations.append(
            "📖 Follow OWASP Secure Coding Practices for comprehensive security"
        )

        return recommendations

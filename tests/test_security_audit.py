"""Tests for security audit functionality."""

import pytest

from crackerjack.config.hooks import SecurityLevel
from crackerjack.security.audit import SecurityAuditor


class MockHookResult:
    """Mock hook result for testing."""

    def __init__(self, name: str, status: str, output: str = ""):
        self.name = name
        self.status = status
        self.output = output
        self.error = output


class TestSecurityAuditor:
    """Test security auditor functionality."""

    def test_critical_security_failure_blocks_publishing(self):
        """Test that critical security failures block publishing."""
        auditor = SecurityAuditor()

        # Mock results with critical failure
        fast_results = [
            MockHookResult("gitleaks", "failed", "Secret detected in code"),
        ]
        comprehensive_results = [
            MockHookResult("bandit", "passed", ""),
        ]

        audit_report = auditor.audit_hook_results(fast_results, comprehensive_results)

        assert audit_report.has_critical_failures
        assert not audit_report.allows_publishing
        assert len(audit_report.critical_failures) == 1
        assert audit_report.critical_failures[0].hook_name == "gitleaks"

    def test_all_critical_pass_allows_publishing(self):
        """Test that passing critical checks allows publishing."""
        auditor = SecurityAuditor()

        fast_results = [
            MockHookResult("gitleaks", "passed", ""),
        ]
        comprehensive_results = [
            MockHookResult("bandit", "passed", ""),
            MockHookResult("pyright", "passed", ""),
        ]

        audit_report = auditor.audit_hook_results(fast_results, comprehensive_results)

        assert not audit_report.has_critical_failures
        assert audit_report.allows_publishing
        assert len(audit_report.critical_failures) == 0

    def test_non_critical_failures_allow_publishing(self):
        """Test that non-critical failures don't block publishing."""
        auditor = SecurityAuditor()

        fast_results = [
            MockHookResult("gitleaks", "passed", ""),
            MockHookResult("ruff-format", "failed", "Formatting issues"),
        ]
        comprehensive_results = [
            MockHookResult("bandit", "passed", ""),
            MockHookResult("pyright", "passed", ""),
            MockHookResult("vulture", "failed", "Dead code found"),
        ]

        audit_report = auditor.audit_hook_results(fast_results, comprehensive_results)

        assert not audit_report.has_critical_failures
        assert audit_report.allows_publishing
        assert len(audit_report.medium_failures) > 0  # vulture, ruff-format

    def test_security_level_classification(self):
        """Test that hooks are classified to correct security levels."""
        auditor = SecurityAuditor()

        # Test critical hooks
        assert auditor._get_hook_security_level("bandit") == SecurityLevel.CRITICAL
        assert auditor._get_hook_security_level("pyright") == SecurityLevel.CRITICAL
        assert auditor._get_hook_security_level("gitleaks") == SecurityLevel.CRITICAL

        # Test high security hooks
        assert (
            auditor._get_hook_security_level("validate-regex-patterns")
            == SecurityLevel.HIGH
        )
        assert auditor._get_hook_security_level("creosote") == SecurityLevel.HIGH

        # Test medium hooks
        assert auditor._get_hook_security_level("ruff-check") == SecurityLevel.MEDIUM
        assert auditor._get_hook_security_level("vulture") == SecurityLevel.MEDIUM

        # Test low security hooks
        assert auditor._get_hook_security_level("ruff-format") == SecurityLevel.LOW
        assert auditor._get_hook_security_level("unknown-hook") == SecurityLevel.LOW

    def test_security_warnings_generation(self):
        """Test that appropriate security warnings are generated."""
        auditor = SecurityAuditor()

        fast_results = [
            MockHookResult("gitleaks", "failed", "Secret detected"),
        ]
        comprehensive_results = [
            MockHookResult("bandit", "failed", "Security issue found"),
        ]

        audit_report = auditor.audit_hook_results(fast_results, comprehensive_results)

        assert len(audit_report.security_warnings) > 0
        critical_warning = audit_report.security_warnings[0]
        assert "CRITICAL" in critical_warning
        assert "2" in critical_warning  # 2 critical failures

    def test_security_recommendations(self):
        """Test that security recommendations are generated."""
        auditor = SecurityAuditor()

        fast_results = [
            MockHookResult("gitleaks", "failed", "Secret detected"),
        ]
        comprehensive_results = [
            MockHookResult("bandit", "failed", "Security issue found"),
        ]

        audit_report = auditor.audit_hook_results(fast_results, comprehensive_results)

        assert len(audit_report.recommendations) > 0
        assert any(
            "Fix all CRITICAL security issues" in rec
            for rec in audit_report.recommendations
        )
        assert any("OWASP" in rec for rec in audit_report.recommendations)


if __name__ == "__main__":
    pytest.main([__file__])

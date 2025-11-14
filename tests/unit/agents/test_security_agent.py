"""Unit tests for SecurityAgent.

Tests security vulnerability detection, regex validation,
hardcoded secrets, shell injection, and various security fixes.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.security_agent import SecurityAgent


@pytest.mark.unit
class TestSecurityAgentInitialization:
    """Test SecurityAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test SecurityAgent initializes correctly."""
        agent = SecurityAgent(context)

        assert agent.context == context

    def test_get_supported_types(self, context):
        """Test agent supports security and regex validation issues."""
        agent = SecurityAgent(context)

        supported = agent.get_supported_types()

        assert IssueType.SECURITY in supported
        assert IssueType.REGEX_VALIDATION in supported


@pytest.mark.unit
@pytest.mark.asyncio
class TestSecurityAgentCanHandle:
    """Test security issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    async def test_can_handle_regex_validation_issue(self, agent):
        """Test high confidence for regex validation issues."""
        issue = Issue(
            id="regex-001",
            type=IssueType.REGEX_VALIDATION,
            severity=Priority.HIGH,
            message="Unsafe regex pattern detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.95

    async def test_can_handle_regex_validation_keyword(self, agent):
        """Test high confidence for regex validation keywords."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="validate-regex-patterns failed for pattern",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.95

    async def test_can_handle_bandit_security_issue(self, agent):
        """Test handling bandit security issues."""
        issue = Issue(
            id="sec-002",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Bandit B602: shell=True detected in subprocess call",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_hardcoded_secret(self, agent):
        """Test handling hardcoded secret issues."""
        issue = Issue(
            id="sec-003",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Hardcoded password detected in source code",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_shell_injection(self, agent):
        """Test handling shell injection vulnerabilities."""
        issue = Issue(
            id="sec-004",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Potential shell injection vulnerability",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_weak_crypto(self, agent):
        """Test handling weak cryptography issues."""
        issue = Issue(
            id="sec-005",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="MD5 hash algorithm is cryptographically weak",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_pickle_usage(self, agent):
        """Test handling unsafe pickle usage."""
        issue = Issue(
            id="sec-006",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Unsafe pickle.load() usage detected",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_yaml_load(self, agent):
        """Test handling unsafe yaml.load usage."""
        issue = Issue(
            id="sec-007",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="yaml.load() can execute arbitrary code",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_security_file_path(self, agent):
        """Test moderate confidence for security-related file paths."""
        issue = Issue(
            id="sec-008",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Security issue",
            file_path="/path/to/auth/handler.py",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.7

    async def test_can_handle_generic_security_issue(self, agent):
        """Test lower confidence for generic security issues."""
        issue = Issue(
            id="sec-009",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Some security concern",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.6

    async def test_cannot_handle_unsupported_type(self, agent):
        """Test agent cannot handle unsupported issue types."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Formatting issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
class TestSecurityAgentVulnerabilityIdentification:
    """Test vulnerability type identification."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    def test_identify_regex_validation_by_type(self, agent):
        """Test identifying regex validation by issue type."""
        issue = Issue(
            id="regex-001",
            type=IssueType.REGEX_VALIDATION,
            severity=Priority.HIGH,
            message="Invalid regex pattern",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "regex_validation"

    def test_identify_regex_validation_by_keyword(self, agent):
        """Test identifying regex validation by keyword."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="validate-regex-patterns found unsafe pattern",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "regex_validation"

    def test_identify_hardcoded_temp_paths(self, agent):
        """Test identifying hardcoded temp paths."""
        issue = Issue(
            id="sec-002",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Bandit B108: hardcoded temp path detected",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "hardcoded_temp_paths"

    def test_identify_shell_injection(self, agent):
        """Test identifying shell injection."""
        issue = Issue(
            id="sec-003",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Bandit B602: shell=True detected",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "shell_injection"

    def test_identify_pickle_usage(self, agent):
        """Test identifying unsafe pickle usage."""
        issue = Issue(
            id="sec-004",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Bandit B301: pickle usage with untrusted data",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "pickle_usage"

    def test_identify_unsafe_yaml(self, agent):
        """Test identifying unsafe YAML loading."""
        issue = Issue(
            id="sec-005",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Bandit B506: yaml.load() usage detected",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "unsafe_yaml"

    def test_identify_weak_crypto(self, agent):
        """Test identifying weak cryptography."""
        issue = Issue(
            id="sec-006",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="MD5 hash function is cryptographically broken",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "weak_crypto"

    def test_identify_jwt_secrets(self, agent):
        """Test identifying JWT secret issues."""
        issue = Issue(
            id="sec-007",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Hardcoded JWT secret key detected",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "jwt_secrets"

    def test_identify_unknown(self, agent):
        """Test identifying unknown vulnerability type."""
        issue = Issue(
            id="sec-008",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Some other security issue",
        )

        vulnerability = agent._identify_vulnerability_type(issue)

        assert vulnerability == "unknown"


@pytest.mark.unit
class TestSecurityAgentPatternChecks:
    """Test pattern checking helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    def test_is_regex_validation_issue_by_type(self, agent):
        """Test regex validation issue identification by type."""
        issue = Issue(
            id="regex-001",
            type=IssueType.REGEX_VALIDATION,
            severity=Priority.HIGH,
            message="Pattern issue",
        )

        result = agent._is_regex_validation_issue(issue)

        assert result is True

    def test_is_regex_validation_issue_by_keyword(self, agent):
        """Test regex validation issue identification by keyword."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="raw regex pattern detected",
        )

        result = agent._is_regex_validation_issue(issue)

        assert result is True

    def test_is_not_regex_validation_issue(self, agent):
        """Test non-regex validation issue."""
        issue = Issue(
            id="sec-002",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="shell injection vulnerability",
        )

        result = agent._is_regex_validation_issue(issue)

        assert result is False

    def test_check_bandit_patterns_b108(self, agent):
        """Test checking Bandit B108 pattern."""
        result = agent._check_bandit_patterns("Bandit B108: hardcoded temp")

        assert result == "hardcoded_temp_paths"

    def test_check_bandit_patterns_b602(self, agent):
        """Test checking Bandit B602 pattern."""
        result = agent._check_bandit_patterns("Bandit B602: shell=True")

        assert result == "shell_injection"

    def test_check_bandit_patterns_b301(self, agent):
        """Test checking Bandit B301 pattern."""
        result = agent._check_bandit_patterns("Bandit B301: pickle usage")

        assert result == "pickle_usage"

    def test_check_bandit_patterns_b506(self, agent):
        """Test checking Bandit B506 pattern."""
        result = agent._check_bandit_patterns("Bandit B506: yaml.load")

        assert result == "unsafe_yaml"

    def test_check_bandit_patterns_crypto(self, agent):
        """Test checking weak crypto patterns."""
        result = agent._check_bandit_patterns("Using MD5 hash function")

        assert result == "weak_crypto"

    def test_check_bandit_patterns_no_match(self, agent):
        """Test checking with no matching pattern."""
        result = agent._check_bandit_patterns("Some other issue")

        assert result is None

    def test_is_jwt_secret_issue(self, agent):
        """Test identifying JWT secret issues."""
        result = agent._is_jwt_secret_issue("Hardcoded JWT secret key")

        assert result is True

    def test_is_not_jwt_secret_issue(self, agent):
        """Test non-JWT secret issues."""
        result = agent._is_jwt_secret_issue("Some other secret")

        assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestSecurityAgentAnalyzeAndFix:
    """Test security issue analysis and fixing."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    async def test_analyze_and_fix_with_fixes_applied(self, agent):
        """Test successful security fix application."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Bandit B602: shell=True detected",
            file_path=None,
        )

        with patch.object(agent, "_identify_vulnerability_type", return_value="shell_injection"):
            with patch.object(agent, "_apply_vulnerability_fixes") as mock_apply:
                mock_apply.return_value = (["Fixed shell injection"], [])
                with patch.object(agent, "_apply_additional_fixes") as mock_additional:
                    mock_additional.return_value = (["Fixed shell injection"], [])

                    result = await agent.analyze_and_fix(issue)

                    assert result.success is True
                    assert result.confidence == 0.95
                    assert len(result.fixes_applied) > 0

    async def test_analyze_and_fix_no_fixes_applied(self, agent):
        """Test when no fixes can be applied."""
        issue = Issue(
            id="sec-002",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Unknown security issue",
        )

        with patch.object(agent, "_identify_vulnerability_type", return_value="unknown"):
            with patch.object(agent, "_apply_vulnerability_fixes") as mock_apply:
                mock_apply.return_value = ([], [])
                with patch.object(agent, "_apply_additional_fixes") as mock_additional:
                    mock_additional.return_value = ([], [])

                    result = await agent.analyze_and_fix(issue)

                    assert result.success is False
                    assert result.confidence == 0.4
                    assert len(result.recommendations) > 0

    async def test_analyze_and_fix_error_handling(self, agent):
        """Test error handling in analyze_and_fix."""
        issue = Issue(
            id="sec-003",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Security issue",
        )

        with patch.object(agent, "_identify_vulnerability_type", side_effect=Exception("Test error")):
            result = await agent.analyze_and_fix(issue)

            assert result.success is False
            assert result.confidence == 0.0
            assert "Failed to fix" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestSecurityAgentFixMethods:
    """Test specific security fix methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    async def test_apply_vulnerability_fixes_shell_injection(self, agent):
        """Test applying shell injection fixes."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="shell=True detected",
        )

        with patch.object(agent, "_fix_shell_injection") as mock_fix:
            mock_fix.return_value = {"fixes": ["Removed shell=True"], "files": []}

            fixes, files = await agent._apply_vulnerability_fixes(
                "shell_injection", issue, [], []
            )

            mock_fix.assert_called_once_with(issue)
            assert "Removed shell=True" in fixes

    async def test_apply_vulnerability_fixes_hardcoded_secrets(self, agent):
        """Test applying hardcoded secrets fixes."""
        issue = Issue(
            id="sec-002",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Hardcoded password",
        )

        with patch.object(agent, "_fix_hardcoded_secrets") as mock_fix:
            mock_fix.return_value = {"fixes": ["Moved secret to env var"], "files": []}

            fixes, files = await agent._apply_vulnerability_fixes(
                "hardcoded_secrets", issue, [], []
            )

            mock_fix.assert_called_once_with(issue)
            assert "Moved secret to env var" in fixes

    async def test_apply_vulnerability_fixes_unknown_type(self, agent):
        """Test applying fixes for unknown vulnerability type."""
        issue = Issue(
            id="sec-003",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Unknown issue",
        )

        fixes, files = await agent._apply_vulnerability_fixes(
            "unknown", issue, [], []
        )

        assert fixes == []
        assert files == []

    async def test_apply_additional_fixes_no_initial_fixes(self, agent):
        """Test applying additional fixes when no initial fixes applied."""
        issue = Issue(
            id="sec-004",
            type=IssueType.SECURITY,
            severity=Priority.MEDIUM,
            message="Security issue",
        )

        with patch.object(agent, "_run_bandit_analysis") as mock_bandit:
            mock_bandit.return_value = ["Bandit suggestion"]
            with patch.object(agent, "_fix_file_security_issues") as mock_file:
                mock_file.return_value = {"fixes": [], "files": []}

                fixes, files = await agent._apply_additional_fixes(issue, [], [])

                mock_bandit.assert_called_once()
                assert "Bandit suggestion" in fixes

    async def test_apply_additional_fixes_with_file_path(self, agent, tmp_path):
        """Test applying additional fixes with file path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\npassword = 'secret'\n")

        issue = Issue(
            id="sec-005",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Security issue",
            file_path=str(test_file),
        )

        with patch.object(agent, "_run_bandit_analysis") as mock_bandit:
            mock_bandit.return_value = []
            with patch.object(agent, "_fix_file_security_issues") as mock_file:
                mock_file.return_value = {"fixes": ["Fixed file"], "files": []}

                fixes, files = await agent._apply_additional_fixes(
                    issue, ["Previous fix"], []
                )

                mock_file.assert_called_once_with(str(test_file))
                assert "Fixed file" in fixes
                assert str(test_file) in files


@pytest.mark.unit
class TestSecurityAgentRecommendations:
    """Test security recommendations."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    def test_get_security_recommendations(self, agent):
        """Test getting security recommendations."""
        recommendations = agent._get_security_recommendations()

        assert len(recommendations) > 0
        assert any("SAFE_PATTERNS" in rec for rec in recommendations)
        assert any("tempfile" in rec for rec in recommendations)
        assert any("shell=True" in rec for rec in recommendations)
        assert any("environment variables" in rec for rec in recommendations)

    def test_create_error_fix_result(self, agent):
        """Test creating error fix result."""
        error = Exception("Test error message")

        result = agent._create_error_fix_result(error)

        assert result.success is False
        assert result.confidence == 0.0
        assert "Failed to fix" in result.remaining_issues[0]
        assert len(result.recommendations) > 0
        assert any("manual" in rec.lower() for rec in result.recommendations)


@pytest.mark.unit
class TestSecurityAgentPatternUtilities:
    """Test pattern utility methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create SecurityAgent instance."""
        context = AgentContext(project_path=tmp_path)
        return SecurityAgent(context)

    def test_check_enhanced_patterns_weak_crypto(self, agent):
        """Test checking enhanced patterns for weak crypto."""
        with patch("crackerjack.agents.security_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_patterns.__getitem__.return_value = mock_pattern

            result = agent._check_enhanced_patterns("MD5 usage detected")

            assert result == "weak_crypto"

    def test_check_enhanced_patterns_no_match(self, agent):
        """Test checking enhanced patterns with no match."""
        with patch("crackerjack.agents.security_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = False
            mock_patterns.__getitem__.return_value = mock_pattern

            result = agent._check_enhanced_patterns("Some message")

            assert result is None

    def test_check_legacy_patterns(self, agent):
        """Test checking legacy patterns."""
        with patch("crackerjack.agents.security_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = True
            mock_patterns.__getitem__.return_value = mock_pattern

            result = agent._check_legacy_patterns("Hardcoded temp path /tmp/file")

            assert result == "hardcoded_temp_paths"

    def test_check_legacy_patterns_no_match(self, agent):
        """Test checking legacy patterns with no match."""
        with patch("crackerjack.agents.security_agent.SAFE_PATTERNS") as mock_patterns:
            mock_pattern = Mock()
            mock_pattern.test.return_value = False
            mock_patterns.__getitem__.return_value = mock_pattern

            result = agent._check_legacy_patterns("Some message")

            assert result is None

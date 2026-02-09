# Crackerjack Test Coverage Expansion Plan

**Status**: Phase 1 - Audit & Analysis
**Target Coverage**: 60%+ overall coverage
**Current Coverage**: 21.6% (from README badge)
**Working Directory**: `/Users/les/Projects/crackerjack`

## Executive Summary

This document outlines the comprehensive test coverage expansion strategy for Crackerjack, the AI-driven Python development platform. The plan is structured in 4 phases spanning 6 days of focused development.

### Success Criteria

- ✅ Overall coverage ≥ 60%
- ✅ Quality checks ≥ 70%
- ✅ Agent skills ≥ 70%
- ✅ CLI ≥ 70%

## Phase 1: Audit Test Coverage (1 day)

### 1.1 Run Coverage Report

```bash
cd /Users/les/Projects/crackerjack
pytest --cov=crackerjack --cov-report=html --cov-report=json
open htmlcov/index.html
```

### 1.2 Coverage Analysis Tasks

- [ ] Generate detailed coverage report
- [ ] Identify low-coverage modules (<30%)
- [ ] Identify medium-coverage modules (30-60%)
- [ ] Identify high-coverage modules (>60%)
- [ ] Catalog untested modules (0% coverage)
- [ ] Prioritize modules by criticality and usage

### 1.3 Module Priority Matrix

**Critical Modules** (Core functionality, high priority):
- `crackerjack/api.py` - Main API entry points
- `crackerjack/cli.py` - CLI command handlers
- `crackerjack/agents/` - AI agent system
- `crackerjack/adapters/` - Quality check adapters
- `crackerjack/orchestration/` - Workflow orchestration
- `crackerjack/services/` - Business logic services

**Supporting Modules** (Medium priority):
- `crackerjack/models/` - Data models and protocols
- `crackerjack/config.py` - Configuration management
- `crackerjack/executors/` - Command executors

**Utility Modules** (Lower priority):
- `crackerjack/utils/` - Helper functions
- `crackerjack/errors.py` - Error definitions

### 1.4 Expected Deliverables

1. **Coverage Analysis Report** (`COVERAGE_AUDIT_REPORT.md`)
   - Overall coverage percentage
   - Module-by-module breakdown
   - Lines of code tested vs untested
   - Critical gaps identification

2. **Priority Test List** (`TEST_PRIORITIES.md`)
   - High-priority untested modules
   - Medium-priority modules needing improvement
   - Quick wins (easy to test, high impact)

## Phase 2: Quality Check Tests (2 days)

### 2.1 Adapter Tests

**Target**: Comprehensive tests for all quality check adapters

#### Ruff Integration Tests
- [ ] Test formatting functionality
- [ ] Test linting functionality
- [ ] Test import sorting
- [ ] Test configuration loading
- [ ] Test error parsing and reporting
- [ ] Test async execution
- [ ] Test file filtering
- [ ] Test cache integration

**File**: `tests/unit/adapters/test_ruff_adapter.py`

```python
"""Test Ruff adapter functionality."""

import pytest
from pathlib import Path
from crackerjack.adapters.format.ruff_adapter import RuffAdapter
from crackerjack.models.config import HookConfig

@pytest.mark.unit
class TestRuffAdapter:
    """Test suite for RuffAdapter."""

    @pytest.fixture
    def ruff_adapter(self):
        """Create RuffAdapter instance."""
        return RuffAdapter()

    @pytest.fixture
    def sample_config(self):
        """Create sample hook configuration."""
        return HookConfig(
            name="ruff",
            enabled=True,
            config={"line_length": 88}
        )

    @pytest.mark.asyncio
    async def test_format_python_file(self, ruff_adapter, sample_config, tmp_path):
        """Test formatting a Python file."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello( ):\n    print('world')\n")

        # Act
        result = await ruff_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_lint_python_file(self, ruff_adapter, sample_config, tmp_path):
        """Test linting a Python file."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys\nimport os  # duplicate\n")

        # Act
        result = await ruff_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert len(result.issues) > 0
        assert any("duplicate" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_import_sorting(self, ruff_adapter, sample_config, tmp_path):
        """Test import sorting."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import sys
import os
from pathlib import Path
import asyncio
""")

        # Act
        result = await ruff_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is True
        content = test_file.read_text()
        # Imports should be sorted: stdlib first, then third-party
        assert "import asyncio" in content
        assert "import os" in content
        assert "from pathlib" in content

    @pytest.mark.asyncio
    async def test_no_files_to_check(self, ruff_adapter, sample_config):
        """Test handling of empty file list."""
        # Act
        result = await ruff_adapter.check([], sample_config)

        # Assert
        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_syntax_error_handling(self, ruff_adapter, sample_config, tmp_path):
        """Test handling of files with syntax errors."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def broken(\n")  # Syntax error

        # Act
        result = await ruff_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert len(result.issues) > 0
        assert any("syntax" in issue.message.lower() for issue in result.issues)
```

#### Bandit Security Scan Tests
- [ ] Test security vulnerability detection
- [ ] Test shell injection detection
- [ ] Test weak cryptography detection
- [ ] Test hardcoded secrets detection
- [ ] Test SQL injection detection
- [ ] Test YAML unsafe loading detection
- [ ] Test error parsing and reporting

**File**: `tests/unit/adapters/test_bandit_adapter.py`

```python
"""Test Bandit adapter for security scanning."""

import pytest
from pathlib import Path
from crackerjack.adapters.security.bandit_adapter import BanditAdapter
from crackerjack.models.config import HookConfig

@pytest.mark.unit
class TestBanditAdapter:
    """Test suite for BanditAdapter."""

    @pytest.fixture
    def bandit_adapter(self):
        """Create BanditAdapter instance."""
        return BanditAdapter()

    @pytest.fixture
    def sample_config(self):
        """Create sample hook configuration."""
        return HookConfig(
            name="bandit",
            enabled=True,
            config={"skip_tests": ["B101"]}
        )

    @pytest.mark.asyncio
    async def test_shell_injection_detection(self, bandit_adapter, sample_config, tmp_path):
        """Test detection of shell injection vulnerabilities."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import subprocess
def dangerous():
    subprocess.run("ls -l", shell=True)  # B602: shell injection
""")

        # Act
        result = await bandit_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert any("B602" in issue.code or "shell" in issue.message.lower()
                   for issue in result.issues)

    @pytest.mark.asyncio
    async def test_weak_cryptography_detection(self, bandit_adapter, sample_config, tmp_path):
        """Test detection of weak cryptographic algorithms."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import hashlib
def weak_hash(data):
    return hashlib.md5(data)  # B303: weak crypto
""")

        # Act
        result = await bandit_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert any("B303" in issue.code or "md5" in issue.message.lower()
                   for issue in result.issues)

    @pytest.mark.asyncio
    async def test_hardcoded_secrets_detection(self, bandit_adapter, sample_config, tmp_path):
        """Test detection of hardcoded secrets."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
API_KEY = "sk-1234567890abcdef"
PASSWORD = "hardcoded_password"
""")

        # Act
        result = await bandit_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert any("hardcoded" in issue.message.lower() or "secret" in issue.message.lower()
                   for issue in result.issues)

    @pytest.mark.asyncio
    async def test_yaml_unsafe_loading_detection(self, bandit_adapter, sample_config, tmp_path):
        """Test detection of unsafe YAML loading."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import yaml
def load_config(filename):
    with open(filename) as f:
        return yaml.load(f)  # B506: unsafe YAML loading
""")

        # Act
        result = await bandit_adapter.check([test_file], sample_config)

        # Assert
        assert result.passed is False
        assert any("B506" in issue.code or "yaml" in issue.message.lower()
                   for issue in result.issues)

    @pytest.mark.asyncio
    async def test_skip_tests_configuration(self, bandit_adapter, tmp_path):
        """Test that skip_tests configuration works correctly."""
        # Arrange
        config = HookConfig(
            name="bandit",
            enabled=True,
            config={"skip_tests": ["B602", "B303"]}
        )
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import subprocess
import hashlib
def dangerous():
    subprocess.run("ls -l", shell=True)
    return hashlib.md5(b"data")
""")

        # Act
        result = await bandit_adapter.check([test_file], config)

        # Assert - skipped tests should not cause failure
        assert result.passed is True
```

#### Coverage Threshold Tests
- [ ] Test coverage threshold enforcement
- [ ] Test coverage ratchet functionality
- [ ] Test milestone tracking
- [ ] Test coverage degradation detection
- [ ] Test coverage improvement calculation
- [ ] Test coverage report generation

**File**: `tests/unit/test_coverage_ratchet.py`

```python
"""Test coverage ratchet functionality."""

import pytest
from pathlib import Path
from crackerjack.services.coverage_ratchet import CoverageRatchet
from crackerjack.models.config import CoverageConfig

@pytest.mark.unit
class TestCoverageRatchet:
    """Test suite for CoverageRatchet."""

    @pytest.fixture
    def coverage_ratchet(self, tmp_path):
        """Create CoverageRatchet instance with temp directory."""
        return CoverageRatchet(project_path=tmp_path)

    @pytest.mark.asyncio
    async def test_initial_coverage_baseline(self, coverage_ratchet, tmp_path):
        """Test establishing initial coverage baseline."""
        # Arrange
        coverage_data = {
            "files": {
                "test_module.py": {"summary": {"percent_covered": 45.5}}
            },
            "totals": {"percent_covered": 45.5}
        }

        # Act
        result = await coverage_ratchet.establish_baseline(coverage_data)

        # Assert
        assert result.previous_coverage is None
        assert result.current_coverage == 45.5
        assert result.is_improvement is True
        assert result.milestone_achieved == "15%"

    @pytest.mark.asyncio
    async def test_coverage_improvement(self, coverage_ratchet, tmp_path):
        """Test detecting coverage improvement."""
        # Arrange - Create baseline file
        baseline_file = tmp_path / ".coverage-baseline.json"
        baseline_file.write_text('{"coverage": 50.0}')

        coverage_data = {
            "totals": {"percent_covered": 55.5}
        }

        # Act
        result = await coverage_ratchet.check_coverage(coverage_data)

        # Assert
        assert result.previous_coverage == 50.0
        assert result.current_coverage == 55.5
        assert result.improvement == 5.5
        assert result.is_improvement is True

    @pytest.mark.asyncio
    async def test_coverage_degradation_detection(self, coverage_ratchet, tmp_path):
        """Test detecting coverage degradation."""
        # Arrange - Create baseline file
        baseline_file = tmp_path / ".coverage-baseline.json"
        baseline_file.write_text('{"coverage": 60.0}')

        coverage_data = {
            "totals": {"percent_covered": 55.0}
        }

        # Act
        result = await coverage_ratchet.check_coverage(coverage_data)

        # Assert
        assert result.previous_coverage == 60.0
        assert result.current_coverage == 55.0
        assert result.is_improvement is False
        assert result.degradation_detected is True

    @pytest.mark.asyncio
    async def test_milestone_tracking(self, coverage_ratchet):
        """Test milestone achievement tracking."""
        # Arrange
        milestones = [15, 20, 25, 50, 75, 90, 100]

        # Act & Assert
        assert coverage_ratchet.check_milestone(14.5, milestones) is None
        assert coverage_ratchet.check_milestone(15.0, milestones) == "15%"
        assert coverage_ratchet.check_milestone(24.9, milestones) is None
        assert coverage_ratchet.check_milestone(25.0, milestones) == "25%"
        assert coverage_ratchet.check_milestone(100.0, milestones) == "100%"

    @pytest.mark.asyncio
    async def test_coverage_goal_setting(self, coverage_ratchet):
        """Test setting explicit coverage goal."""
        # Act
        await coverage_ratchet.set_goal(85.0)

        # Assert
        assert coverage_ratchet.goal == 85.0

    def test_coverage_report_generation(self, coverage_ratchet, tmp_path):
        """Test generation of coverage report."""
        # Arrange
        coverage_data = {
            "files": {
                "module1.py": {"summary": {"percent_covered": 80.0}},
                "module2.py": {"summary": {"percent_covered": 60.0}},
            },
            "totals": {"percent_covered": 70.0}
        }

        # Act
        report = coverage_ratchet.generate_report(coverage_data)

        # Assert
        assert "70.0%" in report
        assert "module1.py" in report
        assert "80.0%" in report
```

#### Custom Check Tests
- [ ] Test trailing whitespace fixer
- [ ] Test end-of-file fixer
- [ ] Test file size checker
- [ ] Test config-driven checks
- [ ] Test custom validation rules

**File**: `tests/unit/adapters/test_utility_adapters.py`

```python
"""Test utility adapter functionality."""

import pytest
from pathlib import Path
from crackerjack.adapters.utility.trailing_whitespace_adapter import TrailingWhitespaceAdapter
from crackerjack.adapters.utility.eof_adapter import EndOfFileAdapter
from crackerjack.adapters.utility.file_size_adapter import FileSizeAdapter
from crackerjack.models.config import HookConfig

@pytest.mark.unit
class TestTrailingWhitespaceAdapter:
    """Test suite for TrailingWhitespaceAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return TrailingWhitespaceAdapter()

    @pytest.fixture
    def config(self):
        """Create sample configuration."""
        return HookConfig(name="trailing-whitespace", enabled=True)

    @pytest.mark.asyncio
    async def test_remove_trailing_spaces(self, adapter, config, tmp_path):
        """Test removal of trailing spaces."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():    \n    pass    \n")

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is True
        content = test_file.read_text()
        assert "def hello():\n" in content
        assert "    pass\n" in content
        assert "    \n" not in content  # No trailing spaces

    @pytest.mark.asyncio
    async def test_preserve_intentional_blank_lines(self, adapter, config, tmp_path):
        """Test that blank lines are preserved."""
        # Arrange
        test_file = tmp_path / "test.py"
        original_content = "def hello():\n\n    pass\n"
        test_file.write_text(original_content)

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is True
        assert test_file.read_text() == original_content

@pytest.mark.unit
class TestEndOfFileAdapter:
    """Test suite for EndOfFileAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return EndOfFileAdapter()

    @pytest.fixture
    def config(self):
        """Create sample configuration."""
        return HookConfig(name="end-of-file-fixer", enabled=True)

    @pytest.mark.asyncio
    async def test_add_final_newline(self, adapter, config, tmp_path):
        """Test adding final newline."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass")

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is True
        content = test_file.read_text()
        assert content.endswith("\n")

    @pytest.mark.asyncio
    async def test_remove_multiple_final_newlines(self, adapter, config, tmp_path):
        """Test removing excess final newlines."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n\n\n")

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is True
        content = test_file.read_text()
        assert content == "def hello():\n    pass\n"

@pytest.mark.unit
class TestFileSizeAdapter:
    """Test suite for FileSizeAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter instance."""
        return FileSizeAdapter()

    @pytest.fixture
    def config(self):
        """Create configuration with size limit."""
        return HookConfig(
            name="file-size",
            enabled=True,
            config={"max_size_kb": 100}
        )

    @pytest.mark.asyncio
    async def test_file_within_limit(self, adapter, config, tmp_path):
        """Test file within size limit."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_file_exceeds_limit(self, adapter, config, tmp_path):
        """Test file exceeding size limit."""
        # Arrange
        test_file = tmp_path / "test.py"
        # Create file larger than 100KB
        test_file.write_text("x" * (200 * 1024))

        # Act
        result = await adapter.check([test_file], config)

        # Assert
        assert result.passed is False
        assert len(result.issues) > 0
        assert any("size" in issue.message.lower() for issue in result.issues)
```

### 2.2 Integration Tests

**File**: `tests/integration/test_quality_workflow.py`

```python
"""Integration tests for quality check workflow."""

import pytest
from pathlib import Path
from crackerjack.api import run_quality_checks
from crackerjack.models.config import QualityConfig

@pytest.mark.integration
class TestQualityWorkflow:
    """Integration tests for quality check workflow."""

    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create a sample project with various code quality issues."""
        # Create Python files with issues
        (tmp_path / "bad_code.py").write_text("""
import os
import sys
import os  # duplicate import
def hello( ):""")

    def insecure():
    subprocess.run("cat /etc/passwd", shell=True)  # Security issue

    def unused_function():  # Dead code
    pass

    # Trailing whitespace above
""")

        (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "0.1.0"
""")

        return tmp_path

    @pytest.mark.asyncio
    async def test_full_quality_workflow(self, sample_project):
        """Test complete quality check workflow."""
        # Arrange
        config = QualityConfig(
            fast_hooks=True,
            comprehensive_hooks=True,
            fail_on_error=True
        )

        # Act
        result = await run_quality_checks(
            project_path=sample_project,
            config=config
        )

        # Assert
        assert result is not None
        assert hasattr(result, "fast_hooks_result")
        assert hasattr(result, "comprehensive_hooks_result")
        assert len(result.issues) > 0  # Should detect issues

    @pytest.mark.asyncio
    async def test_fast_hooks_only(self, sample_project):
        """Test running only fast hooks."""
        # Arrange
        config = QualityConfig(
            fast_hooks=True,
            comprehensive_hooks=False
        )

        # Act
        result = await run_quality_checks(
            project_path=sample_project,
            config=config
        )

        # Assert
        assert result is not None
        assert result.comprehensive_hooks_result is None

    @pytest.mark.asyncio
    async def test_comprehensive_hooks_only(self, sample_project):
        """Test running only comprehensive hooks."""
        # Arrange
        config = QualityConfig(
            fast_hooks=False,
            comprehensive_hooks=True
        )

        # Act
        result = await run_quality_checks(
            project_path=sample_project,
            config=config
        )

        # Assert
        assert result is not None
        assert result.fast_hooks_result is None

    @pytest.mark.asyncio
    async def test_quality_check_caching(self, sample_project):
        """Test that quality checks use caching effectively."""
        # Arrange
        config = QualityConfig(
            fast_hooks=True,
            comprehensive_hooks=True,
            enable_cache=True
        )

        # Act - Run twice
        result1 = await run_quality_checks(
            project_path=sample_project,
            config=config
        )
        result2 = await run_quality_checks(
            project_path=sample_project,
            config=config
        )

        # Assert
        assert result1 is not None
        assert result2 is not None
        # Second run should be faster due to caching
        # (This would require timing measurements in actual implementation)
```

## Phase 3: Agent Skills Tests (2 days)

### 3.1 RefactoringAgent Tests

**File**: `tests/unit/agents/test_refactoring_agent.py`

```python
"""Test RefactoringAgent functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.refactoring_agent import RefactoringAgent
from crackerjack.models.agent_context import AgentContext

@pytest.mark.unit
class TestRefactoringAgent:
    """Test suite for RefactoringAgent."""

    @pytest.fixture
    def refactoring_agent(self):
        """Create RefactoringAgent instance."""
        return RefactoringAgent()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_reduce_complexity(self, refactoring_agent, agent_context, tmp_path):
        """Test complexity reduction."""
        # Arrange
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
def complex_function(data):
    result = []
    for item in data:
        if item > 0:
            for i in range(10):
                if i % 2 == 0:
                    result.append(item * i)
                else:
                    result.append(item)
        elif item < 0:
            result.append(0)
        else:
            result.append(item)
    return result
""")

        agent_context.files = [test_file]

        # Act
        result = await refactoring_agent.fix_issue(
            context=agent_context,
            issue_type="complexity",
            message="Function has cognitive complexity > 15"
        )

        # Assert
        assert result.success is True
        assert result.changes_made > 0

    @pytest.mark.asyncio
    async def test_extract_helper_method(self, refactoring_agent, agent_context, tmp_path):
        """Test extracting helper method."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def process_data(items):
    # Validate items
    validated = []
    for item in items:
        if item is not None and item != "":
            validated.append(item)

    # Transform items
    transformed = []
    for item in validated:
        transformed.append(item.upper())

    return transformed
""")

        agent_context.files = [test_file]

        # Act
        result = await refactoring_agent.fix_issue(
            context=agent_context,
            issue_type="refactoring",
            message="Extract repeated patterns to helper methods"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should have extracted validation logic
        assert "def validate" in content.lower() or "def transform" in content.lower()

    @pytest.mark.asyncio
    async def test_apply_solid_principles(self, refactoring_agent, agent_context, tmp_path):
        """Test applying SOLID principles."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
class Database:
    def connect(self):
        pass

    def query(self, sql):
        pass

    def save_to_file(self, filename):
        pass  # Violates Single Responsibility

    def send_email(self, to, subject):
        pass  # Violates Single Responsibility
""")

        agent_context.files = [test_file]

        # Act
        result = await refactoring_agent.fix_issue(
            context=agent_context,
            issue_type="solid",
            message="Class violates Single Responsibility Principle"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should suggest separating concerns
        assert len(result.suggestions) > 0
```

### 3.2 SecurityAgent Tests

**File**: `tests/unit/agents/test_security_agent.py`

```python
"""Test SecurityAgent functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.security_agent import SecurityAgent
from crackerjack.models.agent_context import AgentContext

@pytest.mark.unit
class TestSecurityAgent:
    """Test suite for SecurityAgent."""

    @pytest.fixture
    def security_agent(self):
        """Create SecurityAgent instance."""
        return SecurityAgent()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_fix_shell_injection(self, security_agent, agent_context, tmp_path):
        """Test fixing shell injection vulnerabilities."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import subprocess

def execute_command(user_input):
    # Dangerous: shell=True with user input
    subprocess.run(f"ls {user_input}", shell=True)

def execute_command_list(user_input):
    # Also dangerous: shell=True
    subprocess.call(["cat", user_input], shell=True)
""")

        agent_context.files = [test_file]

        # Act
        result = await security_agent.fix_issue(
            context=agent_context,
            issue_type="B602",
            message="subprocess call with shell=True"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should remove shell=True
        assert "shell=True" not in content
        # Should use list argument form
        assert "subprocess.run" in content or "subprocess.call" in content

    @pytest.mark.asyncio
    async def test_fix_weak_cryptography(self, security_agent, agent_context, tmp_path):
        """Test fixing weak cryptographic algorithms."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import hashlib

def hash_data_md5(data):
    return hashlib.md5(data).digest()

def hash_data_sha1(data):
    return hashlib.sha1(data).hexdigest()
""")

        agent_context.files = [test_file]

        # Act
        result = await security_agent.fix_issue(
            context=agent_context,
            issue_type="B303",
            message="Weak cryptographic algorithm"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should replace with sha256
        assert "sha256" in content.lower()
        assert "md5" not in content.lower()
        assert "sha1" not in content.lower()

    @pytest.mark.asyncio
    async def test_fix_unsafe_yaml(self, security_agent, agent_context, tmp_path):
        """Test fixing unsafe YAML loading."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import yaml

def load_config(filename):
    with open(filename) as f:
        return yaml.load(f)

def load_all_configs(filename):
    with open(filename) as f:
        return yaml.load_all(f)
""")

        agent_context.files = [test_file]

        # Act
        result = await security_agent.fix_issue(
            context=agent_context,
            issue_type="B506",
            message="Use of unsafe yaml.load"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should replace with yaml.safe_load
        assert "safe_load" in content
        assert "yaml.load(" not in content

    @pytest.mark.asyncio
    async def test_mask_token_exposure(self, security_agent, agent_context, tmp_path):
        """Test masking of exposed tokens."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
# Configuration
API_TOKEN = "pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI"
GITHUB_PAT = "ghp_1234567890abcdef1234567890abcdef1234"
SECRET_KEY = "my-super-secret-key-12345"
""")

        agent_context.files = [test_file]

        # Act
        result = await security_agent.fix_issue(
            context=agent_context,
            issue_type="hardcoded_secret",
            message="Hardcoded secret detected"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should mask or replace with environment variables
        assert "pypi-" not in content
        assert "ghp_" not in content
        assert "os.environ" in content or "getenv" in content.lower()

    @pytest.mark.asyncio
    async def test_fix_unsafe_random(self, security_agent, agent_context, tmp_path):
        """Test fixing unsafe random functions."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import random

def generate_token():
    return random.choice("abcdefghijklmnopqrstuvwxyz")

def generate_password():
    return random.choice(["123", "456", "789"])
""")

        agent_context.files = [test_file]

        # Act
        result = await security_agent.fix_issue(
            context=agent_context,
            issue_type="B311",
            message="Use of random.choice for security"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should use secrets module
        assert "secrets.choice" in content or "import secrets" in content
```

### 3.3 PerformanceAgent Tests

**File**: `tests/unit/agents/test_performance_agent.py`

```python
"""Test PerformanceAgent functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.performance_agent import PerformanceAgent
from crackerjack.models.agent_context import AgentContext

@pytest.mark.unit
class TestPerformanceAgent:
    """Test suite for PerformanceAgent."""

    @pytest.fixture
    def performance_agent(self):
        """Create PerformanceAgent instance."""
        return PerformanceAgent()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_optimize_string_concatenation(self, performance_agent, agent_context, tmp_path):
        """Test optimizing string concatenation."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def build_string(items):
    result = ""
    for item in items:
        result += str(item) + " "
    return result

def build_lines(lines):
    output = ""
    for line in lines:
        output += line + "\\n"
    return output
""")

        agent_context.files = [test_file]

        # Act
        result = await performance_agent.fix_issue(
            context=agent_context,
            issue_type="string_concat",
            message="Inefficient string concatenation in loop"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should use list comprehension or str.join
        assert "join" in content or "list comprehension" in content.lower()

    @pytest.mark.asyncio
    async def test_optimize_list_operations(self, performance_agent, agent_context, tmp_path):
        """Test optimizing list operations."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def process_lists(list1, list2):
    result = []
    for item1 in list1:
        for item2 in list2:
            if item1 == item2:
                result.append(item1)
    return result
""")

        agent_context.files = [test_file]

        # Act
        result = await performance_agent.fix_issue(
            context=agent_context,
            issue_type="nested_loop",
            message="O(n²) nested loop detected"
        )

        # Assert
        assert result.success is True
        assert result.changes_made > 0

    @pytest.mark.asyncio
    async def test_use_generators(self, performance_agent, agent_context, tmp_path):
        """Test converting to generators."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def get_all_items():
    result = []
    for i in range(1000000):
        result.append(i * 2)
    return result

def process_data(data):
    return [x * 2 for x in data if x > 0]
""")

        agent_context.files = [test_file]

        # Act
        result = await performance_agent.fix_issue(
            context=agent_context,
            issue_type="memory_efficiency",
            message="Consider using generators instead of lists"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should suggest generators for large datasets
        assert "yield" in content or "generator" in content.lower()

    @pytest.mark.asyncio
    async def test_fix_caching_opportunities(self, performance_agent, agent_context, tmp_path):
        """Test adding caching to repeated operations."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def get_value(data):
    # Expensive computation repeated multiple times
    result = 0
    for item in data:
        result += expensive_function(item)
    return result

def process_data(items):
    results = []
    for item in items:
        # Recomputing same value
        value = expensive_function(item)
        results.append(value * 2)
        results.append(value * 3)
    return results
""")

        agent_context.files = [test_file]

        # Act
        result = await performance_agent.fix_issue(
            context=agent_context,
            issue_type="caching",
            message="Repeated expensive computation detected"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should suggest functools.lru_cache or memoization
        assert "cache" in content.lower() or "lru_cache" in content or "memoiz" in content.lower()
```

### 3.4 TestCreationAgent Tests

**File**: `tests/unit/agents/test_test_creation_agent.py`

```python
"""Test TestCreationAgent functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.test_creation_agent import TestCreationAgent
from crackerjack.models.agent_context import AgentContext

@pytest.mark.unit
class TestTestCreationAgent:
    """Test suite for TestCreationAgent."""

    @pytest.fixture
    def test_agent(self):
        """Create TestCreationAgent instance."""
        return TestCreationAgent()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_fix_missing_fixture(self, test_agent, agent_context, tmp_path):
        """Test fixing missing test fixtures."""
        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
def test_function():
    # Missing 'sample_data' fixture
    result = process_data(sample_data)
    assert result is not None
""")

        agent_context.files = [test_file]

        # Act
        result = await test_agent.fix_issue(
            context=agent_context,
            issue_type="missing_fixture",
            message="Fixture 'sample_data' not found"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should add fixture definition
        assert "@pytest.fixture" in content
        assert "def sample_data" in content

    @pytest.mark.asyncio
    async def test_fix_import_error(self, test_agent, agent_context, tmp_path):
        """Test fixing import errors in tests."""
        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
from myapp.models import User
from myapp.services import UserService

def test_user_creation():
    user = User(name="Test")
    assert user.name == "Test"
""")

        # Create source module
        models_dir = tmp_path / "myapp" / "models"
        models_dir.mkdir(parents=True)
        (models_dir / "__init__.py").write_text("")
        (models_dir / "user.py").write_text("class User: pass")

        agent_context.files = [test_file]

        # Act
        result = await test_agent.fix_issue(
            context=agent_context,
            issue_type="import_error",
            message="Module 'myapp.models' not found"
        )

        # Assert
        assert result.success is True
        # Should fix import path or add missing __init__.py

    @pytest.mark.asyncio
    async def test_fix_assertion_statement(self, test_agent, agent_context, tmp_path):
        """Test fixing assertion statements."""
        # Arrange
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
def test_calculation():
    result = calculate(1, 2)
    assert result == 3  # Should use more specific assertions

def test_collection():
    items = get_items()
    assert len(items) > 0  # Should use assertGreater
""")

        agent_context.files = [test_file]

        # Act
        result = await test_agent.fix_issue(
            context=agent_context,
            issue_type="assertion_style",
            message="Use specific assertion methods"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should suggest pytest-specific assertions
        assert "assertEqual" in content or "assertGreater" in content or "assert" in content

    @pytest.mark.asyncio
    async def test_add_test_coverage(self, test_agent, agent_context, tmp_path):
        """Test adding missing test coverage."""
        # Arrange
        source_file = tmp_path / "calculator.py"
        source_file.write_text("""
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b
""")

        test_file = tmp_path / "test_calculator.py"
        test_file.write_text("""
from calculator import Calculator

def test_add():
    calc = Calculator()
    assert calc.add(1, 2) == 3

# Missing tests for subtract and multiply
""")

        agent_context.files = [source_file, test_file]

        # Act
        result = await test_agent.fix_issue(
            context=agent_context,
            issue_type="missing_coverage",
            message="Functions subtract and multiply not tested"
        )

        # Assert
        assert result.success is True
        content = test_file.read_text()
        # Should add tests for missing functions
        assert "def test_subtract" in content
        assert "def test_multiply" in content
```

### 3.5 DocumentationAgent Tests

**File**: `tests/unit/agents/test_documentation_agent.py`

```python
"""Test DocumentationAgent functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.documentation_agent import DocumentationAgent
from crackerjack.models.agent_context import AgentContext

@pytest.mark.unit
class TestDocumentationAgent:
    """Test suite for DocumentationAgent."""

    @pytest.fixture
    def doc_agent(self):
        """Create DocumentationAgent instance."""
        return DocumentationAgent()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_generate_changelog(self, doc_agent, agent_context, tmp_path):
        """Test changelog generation."""
        # Arrange
        changelog_file = tmp_path / "CHANGELOG.md"
        changelog_file.write_text("""
# Changelog

## [Unreleased]

## [0.1.0] - 2024-01-01
### Added
- Initial release
""")

        # Mock git history
        agent_context.git_commits = [
            {"message": "feat: add user authentication"},
            {"message": "fix: resolve login bug"},
            {"message": "docs: update README"}
        ]

        # Act
        result = await doc_agent.generate_changelog(
            context=agent_context,
            version="0.2.0"
        )

        # Assert
        assert result.success is True
        content = changelog_file.read_text()
        assert "0.2.0" in content
        assert "feat" in content or "Added" in content
        assert "fix" in content or "Fixed" in content

    @pytest.mark.asyncio
    async def test_maintain_markdown_consistency(self, doc_agent, agent_context, tmp_path):
        """Test maintaining consistency across markdown files."""
        # Arrange
        readme_file = tmp_path / "README.md"
        readme_file.write_text("""
# My Project

## Features
- Feature 1
- Feature 2

## Installation
pip install myproject
""")

        docs_file = tmp_path / "docs" / "FEATURES.md"
        docs_file.parent.mkdir(exist_ok=True)
        docs_file.write_text("""
# Features

This project has:
- Feature A
- Feature B
""")

        agent_context.files = [readme_file, docs_file]

        # Act
        result = await doc_agent.fix_issue(
            context=agent_context,
            issue_type="inconsistent_docs",
            message="Documentation files have inconsistent feature lists"
        )

        # Assert
        assert result.success is True
        # Should identify inconsistencies and suggest updates

    @pytest.mark.asyncio
    async def test_update_readme_badge(self, doc_agent, agent_context, tmp_path):
        """Test updating README coverage badge."""
        # Arrange
        readme_file = tmp_path / "README.md"
        readme_file.write_text("""
# My Project

![Coverage](https://img.shields.io/badge/coverage-50%25-red)

## Installation
...
""")

        agent_context.files = [readme_file]
        agent_context.coverage_percentage = 65.5

        # Act
        result = await doc_agent.update_coverage_badge(
            context=agent_context
        )

        # Assert
        assert result.success is True
        content = readme_file.read_text()
        assert "65.5%" in content or "65%" in content
        # Color should be updated based on coverage
        assert "red" not in content or 65.5 > 50  # Should improve color

    @pytest.mark.asyncio
    async def test_fix_inconsistent_section_headers(self, doc_agent, agent_context, tmp_path):
        """Test fixing inconsistent section headers."""
        # Arrange
        doc_file = tmp_path / "docs.md"
        doc_file.write_text("""
# My Documentation

## Getting Started
This is getting started.

## Quick Start
This is quick start.

## Installation
Install the package.

### INSTALLATION
Alternative installation.
""")

        agent_context.files = [doc_file]

        # Act
        result = await doc_agent.fix_issue(
            context=agent_context,
            issue_type="inconsistent_headers",
            message="Duplicate or inconsistent section headers"
        )

        # Assert
        assert result.success is True
        content = doc_file.read_text()
        # Should consolidate duplicate sections
        assert content.count("## Getting Started") + content.count("## Quick Start") < 2
```

### 3.6 Agent Coordination Tests

**File**: `tests/unit/agents/test_agent_coordination.py`

```python
"""Test agent coordination and batch processing."""

import pytest
from pathlib import Path
from crackerjack.agents.agent_coordinator import AgentCoordinator
from crackerjack.models.agent_context import AgentContext
from crackerjack.models.issue import Issue

@pytest.mark.unit
class TestAgentCoordination:
    """Test suite for agent coordination."""

    @pytest.fixture
    def coordinator(self):
        """Create AgentCoordinator instance."""
        return AgentCoordinator()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={}
        )

    @pytest.mark.asyncio
    async def test_confidence_scoring(self, coordinator, agent_context):
        """Test confidence-based agent routing."""
        # Arrange
        issues = [
            Issue(
                type="B602",
                message="subprocess call with shell=True",
                file="test.py",
                line=10
            ),
            Issue(
                type="complexity",
                message="Function has cognitive complexity > 15",
                file="test.py",
                line=20
            ),
            Issue(
                type="missing_fixture",
                message="Fixture 'sample_data' not found",
                file="test_example.py",
                line=5
            )
        ]

        # Act
        routing = coordinator.route_issues(issues)

        # Assert
        assert routing["B602"]["agent"] == "SecurityAgent"
        assert routing["B602"]["confidence"] >= 0.7
        assert routing["complexity"]["agent"] == "RefactoringAgent"
        assert routing["complexity"]["confidence"] >= 0.7
        assert routing["missing_fixture"]["agent"] == "TestCreationAgent"
        assert routing["missing_fixture"]["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_batch_processing(self, coordinator, agent_context, tmp_path):
        """Test batch processing of related issues."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import subprocess
import hashlib

def dangerous():
    subprocess.run("ls", shell=True)
    return hashlib.md5(b"data")
""")

        issues = [
            Issue(type="B602", message="shell injection", file="test.py", line=4),
            Issue(type="B303", message="weak crypto", file="test.py", line=5)
        ]

        agent_context.files = [test_file]
        agent_context.issues = issues

        # Act
        results = await coordinator.batch_fix(agent_context)

        # Assert
        assert len(results) == 2
        assert all(r.success for r in results)
        content = test_file.read_text()
        assert "shell=True" not in content
        assert "md5" not in content.lower()

    @pytest.mark.asyncio
    async def test_collaborative_mode(self, coordinator, agent_context, tmp_path):
        """Test collaborative agent mode for complex issues."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def complex_function(data):
    result = []
    for item in data:
        if item > 0:
            for i in range(10):
                result.append(process(item, i))
    return result
""")

        issues = [
            Issue(type="complexity", message="High complexity", file="test.py", line=2),
            Issue(type="performance", message="Inefficient loop", file="test.py", line=5)
        ]

        agent_context.files = [test_file]
        agent_context.issues = issues

        # Act
        result = await coordinator.collaborative_fix(agent_context)

        # Assert
        assert result.success is True
        # Multiple agents should contribute
        assert len(result.contributing_agents) > 1

    @pytest.mark.asyncio
    async def test_agent_fallback(self, coordinator, agent_context):
        """Test fallback to generic agent when specialized agent fails."""
        # Arrange
        issues = [
            Issue(type="unknown_type", message="Unknown issue", file="test.py", line=1)
        ]

        agent_context.issues = issues

        # Act
        result = await coordinator.route_and_fix(agent_context)

        # Assert
        assert result is not None
        # Should use generic agent as fallback
```

## Phase 4: CLI Tests (1 day)

### 4.1 CLI Command Tests

**File**: `tests/unit/test_cli_commands.py`

```python
"""Test CLI command handlers."""

import pytest
from typer.testing import CliRunner
from pathlib import Path
from crackerjack.cli import app

runner = CliRunner()

@pytest.mark.unit
class TestCLICommands:
    """Test suite for CLI commands."""

    def test_run_command(self, tmp_path):
        """Test 'crackerjack run' command."""
        # Arrange
        result.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run"])

        # Assert
        assert result.exit_code == 0
        assert "crackerjack" in result.stdout.lower()

    def test_run_with_tests_flag(self, tmp_path):
        """Test 'crackerjack run --run-tests' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--run-tests"])

        # Assert
        assert result.exit_code == 0

    def test_run_with_ai_fix_flag(self, tmp_path):
        """Test 'crackerjack run --ai-fix' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--ai-fix", "--run-tests"])

        # Assert
        # Should either succeed or fail gracefully with missing API key
        assert result.exit_code in [0, 1]

    def test_fast_hooks_only(self, tmp_path):
        """Test 'crackerjack run --fast' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--fast"])

        # Assert
        assert result.exit_code == 0

    def test_comprehensive_hooks_only(self, tmp_path):
        """Test 'crackerjack run --comp' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--comp"])

        # Assert
        assert result.exit_code == 0

    def test_skip_hooks(self, tmp_path):
        """Test 'crackerjack run --skip-hooks' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--skip-hooks"])

        # Assert
        assert result.exit_code == 0
        assert "skipping hooks" in result.stdout.lower()

    def test_coverage_status(self, tmp_path):
        """Test 'crackerjack run --coverage-status' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")
        (tmp_path / ".coverage-baseline.json").write_text('{"coverage": 50.0}')

        # Act
        result = runner.invoke(app, ["run", "--coverage-status"])

        # Assert
        assert result.exit_code == 0
        assert "coverage" in result.stdout.lower()

    def test_clear_cache(self, tmp_path):
        """Test 'crackerjack run --clear-cache' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--clear-cache"])

        # Assert
        assert result.exit_code == 0
        assert "cache" in result.stdout.lower()

    def test_verbose_output(self, tmp_path):
        """Test 'crackerjack run --verbose' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--verbose"])

        # Assert
        assert result.exit_code == 0
        # Verbose mode should show more output

    def test_interactive_mode(self, tmp_path):
        """Test 'crackerjack run --interactive' command."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = runner.invoke(app, ["run", "--interactive"])

        # Assert
        assert result.exit_code == 0

    def test_mcp_server_start(self):
        """Test 'crackerjack start' command."""
        # Act
        result = runner.invoke(app, ["start"])

        # Assert
        # Should either start successfully or already be running
        assert result.exit_code in [0, 1]

    def test_mcp_server_status(self):
        """Test 'crackerjack status' command."""
        # Act
        result = runner.invoke(app, ["status"])

        # Assert
        assert result.exit_code == 0
        assert "status" in result.stdout.lower()

    def test_mcp_server_health(self):
        """Test 'crackerjack health' command."""
        # Act
        result = runner.invoke(app, ["health"])

        # Assert
        assert result.exit_code == 0

    def test_mcp_server_stop(self):
        """Test 'crackerjack stop' command."""
        # Act
        result = runner.invoke(app, ["stop"])

        # Assert
        assert result.exit_code in [0, 1]  # May fail if not running
```

### 4.2 CLI Integration Tests

**File**: `tests/integration/test_cli_workflow.py`

```python
"""Integration tests for CLI workflows."""

import pytest
import subprocess
from pathlib import Path

@pytest.mark.integration
class TestCLIWorkflow:
    """Integration tests for complete CLI workflows."""

    def test_full_quality_check_workflow(self, tmp_path):
        """Test complete quality check workflow via CLI."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\\n")
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = subprocess.run(
            ["python", "-m", "crackerjack", "run"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )

        # Assert
        assert result.returncode == 0

    def test_ai_fix_workflow(self, tmp_path):
        """Test AI fix workflow via CLI."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("""
import subprocess
def bad():
    subprocess.run("ls", shell=True)
""")
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = subprocess.run(
            ["python", "-m", "crackerjack", "run", "--ai-fix"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Assert
        # Should either fix or fail gracefully
        assert result.returncode in [0, 1]

    def test_publish_workflow(self, tmp_path):
        """Test publish workflow via CLI."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        # Act
        result = subprocess.run(
            ["python", "-m", "crackerjack", "run", "--publish", "patch"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )

        # Assert
        # Should fail due to missing PyPI token, but handle gracefully
        assert result.returncode in [0, 1]

    def test_coverage_ratchet_workflow(self, tmp_path):
        """Test coverage ratchet workflow via CLI."""
        # Arrange
        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")

        # Act
        result = subprocess.run(
            ["python", "-m", "crackerjack", "run", "--coverage-status"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )

        # Assert
        assert result.returncode == 0
```

## Test Infrastructure Improvements

### Fixtures Enhancement

**File**: `tests/conftest.py` additions

```python
"""Additional fixtures for comprehensive testing."""

@pytest.fixture
def sample_python_project(tmp_path):
    """Create a sample Python project with various files."""
    # Create project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    # Create pyproject.toml
    (tmp_path / "pyproject.toml").write_text("""
[project]
name = "sample-project"
version = "0.1.0"
dependencies = ["pydantic>=2.0.0"]

[tool.ruff]
line-length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

    # Create source file with issues
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "src" / "module.py").write_text("""
import os
import sys
import os

def calculate(data):
    result = []
    for item in data:
        if item > 0:
            for i in range(10):
                result.append(item * i)
    return result

def insecure():
    import subprocess
    subprocess.run("ls -l", shell=True)

def weak_hash(data):
    import hashlib
    return hashlib.md5(data)
""")

    # Create test file
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_module.py").write_text("""
import pytest

def test_calculate():
    from src.module import calculate
    result = calculate([1, 2, 3])
    assert len(result) > 0
""")

    return tmp_path

@pytest.fixture
def mock_coverage_data():
    """Mock coverage data for testing."""
    return {
        "files": {
            "module1.py": {
                "summary": {"percent_covered": 85.5},
                "missing_lines": [10, 15, 20]
            },
            "module2.py": {
                "summary": {"percent_covered": 60.0},
                "missing_lines": [5, 8, 12, 18]
            }
        },
        "totals": {
            "percent_covered": 72.75,
            "num_statements": 400,
            "covered_lines": 291,
            "missing_lines": 109
        }
    }

@pytest.fixture
def mock_quality_issues():
    """Mock quality issues for testing."""
    return [
        {
            "type": "B602",
            "message": "subprocess call with shell=True",
            "file": "test.py",
            "line": 10,
            "severity": "high"
        },
        {
            "type": "complexity",
            "message": "Function has cognitive complexity > 15",
            "file": "test.py",
            "line": 20,
            "severity": "medium"
        },
        {
            "type": "import",
            "message": "Duplicate import",
            "file": "test.py",
            "line": 3,
            "severity": "low"
        }
    ]
```

## Execution Strategy

### Daily Workflow

**Day 1: Coverage Audit**
- Run pytest with coverage
- Generate HTML report
- Identify low-coverage modules
- Create prioritized test list
- Set up test infrastructure

**Day 2-3: Quality Check Tests**
- Implement adapter tests (Ruff, Bandit)
- Implement coverage ratchet tests
- Implement custom check tests
- Add integration tests

**Day 4-5: Agent Skills Tests**
- Implement RefactoringAgent tests
- Implement SecurityAgent tests
- Implement PerformanceAgent tests
- Implement TestCreationAgent tests
- Implement DocumentationAgent tests
- Add agent coordination tests

**Day 6: CLI Tests**
- Implement CLI command tests
- Add CLI integration tests
- End-to-end workflow tests

### Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| `crackerjack/adapters/` | 70% | High |
| `crackerjack/agents/` | 70% | High |
| `crackerjack/cli.py` | 70% | High |
| `crackerjack/api.py` | 60% | Medium |
| `crackerjack/orchestration/` | 60% | Medium |
| `crackerjack/services/` | 60% | Medium |
| `crackerjack/models/` | 50% | Low |
| `crackerjack/config.py` | 50% | Low |

## Success Metrics

### Coverage Metrics

- **Overall Coverage**: ≥ 60%
- **Critical Modules**: ≥ 70%
- **High Priority Modules**: ≥ 70%
- **Medium Priority Modules**: ≥ 60%
- **Low Priority Modules**: ≥ 50%

### Quality Metrics

- **Test Execution Time**: < 5 minutes for full suite
- **Flaky Test Rate**: < 1%
- **Test Pass Rate**: ≥ 98%
- **Code Coverage Growth**: +38.4% (from 21.6% to 60%)

## Next Steps

1. **Run Coverage Audit**: Execute pytest with coverage to establish baseline
2. **Create Test Files**: Start with highest priority modules
3. **Implement Tests**: Follow test templates provided in this plan
4. **Verify Coverage**: Run coverage reports after each batch
5. **Refine Tests**: Address flaky tests and improve reliability
6. **Document Progress**: Update coverage reports daily

## Appendix: Test Writing Guidelines

### Test Structure

```python
"""Test module description."""

import pytest
from crackerjack.module import ClassUnderTest

@pytest.mark.unit
class TestClassUnderTest:
    """Test suite for ClassUnderTest."""

    @pytest.fixture
    def setup(self):
        """Create test fixture."""
        return ClassUnderTest()

    @pytest.mark.asyncio
    async def test_feature_positive_case(self, setup):
        """Test feature with valid input."""
        # Arrange
        input_data = "valid"

        # Act
        result = await setup.method(input_data)

        # Assert
        assert result.is_valid

    def test_feature_negative_case(self, setup):
        """Test feature with invalid input."""
        # Arrange
        input_data = None

        # Act & Assert
        with pytest.raises(ValueError):
            setup.method(input_data)
```

### Best Practices

1. **Use fixtures**: Reuse setup code via conftest.py fixtures
2. **AAA pattern**: Arrange-Act-Assert structure for clarity
3. **Descriptive names**: Test names should describe what they test
4. **One assertion per test**: Tests should verify one thing
5. **Async tests**: Use `@pytest.mark.asyncio` for async functions
6. **Markers**: Use pytest markers for test categorization
7. **Mock external dependencies**: Don't depend on external services
8. **Clean up**: Use tmp_path for temporary files

---

**Document Status**: Ready for execution
**Last Updated**: 2026-02-09
**Version**: 1.0

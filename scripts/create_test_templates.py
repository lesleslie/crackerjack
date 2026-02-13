#!/usr/bin/env python3

from pathlib import Path


def generate_adapter_test_template(adapter_name: str, adapter_class: str) -> str:
    return f'''"""Test {adapter_name} functionality."""

import pytest
from pathlib import Path
from crackerjack.adapters.{adapter_name} import {adapter_class}
from crackerjack.models.config import HookConfig


@pytest.mark.unit
class Test{adapter_class}:
    """Test suite for {adapter_class}."""

    @pytest.fixture
    def adapter(self):
        """Create {adapter_class} instance."""
        return {adapter_class}()

    @pytest.fixture
    def config(self):
        """Create sample hook configuration."""
        return HookConfig(
            name="{adapter_name}",
            enabled=True,
            config={{}}
        )

    @pytest.mark.asyncio
    async def test_check_with_valid_files(self, adapter, config, tmp_path):
        """Test check with valid files."""

        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass\\n")


        result = await adapter.check([test_file], config)


        assert result is not None
        assert hasattr(result, "passed")

    @pytest.mark.asyncio
    async def test_check_with_empty_file_list(self, adapter, config):
        """Test check with empty file list."""

        result = await adapter.check([], config)


        assert result is not None
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_check_with_invalid_file(self, adapter, config, tmp_path):
        """Test check with invalid file."""

        test_file = tmp_path / "test.py"
        test_file.write_text("invalid syntax here[")


        result = await adapter.check([test_file], config)


        assert result is not None

'''


def generate_agent_test_template(agent_name: str, agent_class: str) -> str:
    return f'''"""Test {agent_name} functionality."""

import pytest
from pathlib import Path
from crackerjack.agents.{agent_name} import {agent_class}
from crackerjack.models.agent_context import AgentContext
from crackerjack.models.issue import Issue


@pytest.mark.unit
class Test{agent_class}:
    """Test suite for {agent_class}."""

    @pytest.fixture
    def agent(self):
        """Create {agent_class} instance."""
        return {agent_class}()

    @pytest.fixture
    def agent_context(self, tmp_path):
        """Create agent context."""
        return AgentContext(
            project_path=tmp_path,
            files=[],
            issues=[],
            config={{}}
        )

    @pytest.mark.asyncio
    async def test_fix_issue_basic(self, agent, agent_context, tmp_path):
        """Test basic issue fixing."""

        test_file = tmp_path / "test.py"
        test_file.write_text("# sample code\\n")

        issue = Issue(
            type="test_type",
            message="Test issue message",
            file="test.py",
            line=1
        )

        agent_context.files = [test_file]
        agent_context.issues = [issue]


        result = await agent.fix_issue(
            context=agent_context,
            issue_type=issue.type,
            message=issue.message
        )


        assert result is not None
        assert hasattr(result, "success")

    @pytest.mark.asyncio
    async def test_fix_issue_with_no_files(self, agent, agent_context):
        """Test fixing issue with no files."""

        issue = Issue(
            type="test_type",
            message="Test issue",
            file="test.py",
            line=1
        )

        agent_context.issues = [issue]


        result = await agent.fix_issue(
            context=agent_context,
            issue_type=issue.type,
            message=issue.message
        )


        assert result is not None
'''


def generate_cli_test_template(command: str) -> str:
    return f'''"""Test CLI command: {command}."""

import pytest
from typer.testing import CliRunner
from pathlib import Path
from crackerjack.cli import app

runner = CliRunner()


@pytest.mark.unit
class TestCLI{command.replace("-", " ").title().replace(" ", "")}:
    """Test suite for '{command}' CLI command."""

    def test_{command.replace("-", "_")}_command(self, tmp_path):
        """Test 'crackerjack {command}' command."""

        (tmp_path / "pyproject.toml").write_text("[project]\\nname = 'test'")


        result = runner.invoke(app, ["{command}"])


        assert result.exit_code in [0, 1]
'''


def main():
    base_dir = Path("/Users/les/Projects/crackerjack")
    tests_dir = base_dir / "tests" / "unit"

    adapters = [
        ("format", "ruff_adapter", "RuffAdapter"),
        ("format", "mdformat_adapter", "MdformatAdapter"),
        ("security", "bandit_adapter", "BanditAdapter"),
        ("security", "gitleaks_adapter", "GitleaksAdapter"),
        ("lint", "codespell_adapter", "CodespellAdapter"),
        ("complexity", "complexipy_adapter", "ComplexipyAdapter"),
        ("type", "zuban_adapter", "ZubanAdapter"),
        ("refactor", "refurb_adapter", "RefurbAdapter"),
        ("refactor", "creosote_adapter", "CreosoteAdapter"),
        ("refactor", "skylos_adapter", "SkylosAdapter"),
    ]

    agents = [
        ("refactoring_agent", "RefactoringAgent"),
        ("security_agent", "SecurityAgent"),
        ("performance_agent", "PerformanceAgent"),
        ("test_creation_agent", "TestCreationAgent"),
        ("documentation_agent", "DocumentationAgent"),
    ]

    commands = [
        "run",
        "start",
        "stop",
        "status",
        "health",
    ]

    print("📝 Generating test templates...")
    print()

    print("🔧 Adapter tests:")
    for category, module_name, class_name in adapters:
        output_dir = tests_dir / "adapters" / category
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"test_{module_name}.py"
        template = generate_adapter_test_template(module_name, class_name)

        if not output_file.exists():
            output_file.write_text(template)
            print(f"  ✓ Created: {output_file.relative_to(base_dir)}")
        else:
            print(f"  ⊙ Skipped (exists): {output_file.relative_to(base_dir)}")

    print()
    print("🤖 Agent tests:")
    for module_name, class_name in agents:
        output_dir = tests_dir / "agents"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"test_{module_name}.py"
        template = generate_agent_test_template(module_name, class_name)

        if not output_file.exists():
            output_file.write_text(template)
            print(f"  ✓ Created: {output_file.relative_to(base_dir)}")
        else:
            print(f"  ⊙ Skipped (exists): {output_file.relative_to(base_dir)}")

    print()
    print("💻 CLI tests:")
    for command in commands:
        output_dir = tests_dir / "cli"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"test_cli_{command}.py"
        template = generate_cli_test_template(command)

        if not output_file.exists():
            output_file.write_text(template)
            print(f"  ✓ Created: {output_file.relative_to(base_dir)}")
        else:
            print(f"  ⊙ Skipped (exists): {output_file.relative_to(base_dir)}")

    print()
    print("✅ Test template generation complete!")
    print()
    print("📋 Next steps:")
    print("   1. Review generated templates")
    print("   2. Implement actual test logic")
    print("   3. Run tests with: pytest tests/unit/ -v")
    print()


if __name__ == "__main__":
    main()

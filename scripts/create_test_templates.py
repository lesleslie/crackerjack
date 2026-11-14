#!/usr/bin/env python3

from pathlib import Path


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
    base_dir = Path(__file__).resolve().parent.parent
    tests_dir = base_dir / "tests" / "unit"

    commands = [
        "run",
        "start",
        "stop",
        "status",
        "health",
    ]

    print("📝 Generating test templates...")
    print()

    print("💻 CLI tests:")
    for command in commands:
        output_dir = tests_dir / "cli"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"test_cli_{command}.py"
        template = generate_cli_test_template(command)

        if not output_file.exists():
            output_file.write_text(template)
            print(f" ✓ Created: {output_file.relative_to(base_dir)}")
        else:
            print(f" ⊙ Skipped (exists): {output_file.relative_to(base_dir)}")

    print()
    print("✅ Test template generation complete!")
    print()
    print("📋 Next steps:")
    print(" 1. Review generated templates")
    print(" 2. Implement actual test logic")
    print(" 3. Run tests with: pytest tests/unit/ -v")
    print()


if __name__ == "__main__":
    main()

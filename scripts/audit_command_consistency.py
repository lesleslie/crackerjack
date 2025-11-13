"""Audit command consistency between .pre-commit-config.yaml and tool_commands.py.

Phase 10.4.2: Command Harmonization

This script compares hook definitions in both locations and identifies discrepancies.
"""

import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crackerjack.config.tool_commands import TOOL_COMMANDS


def load_precommit_config() -> dict:
    """Load .pre-commit-config.yaml."""
    config_path = project_root / ".pre-commit-config.yaml"
    with config_path.open() as f:
        return yaml.safe_load(f)


def extract_precommit_commands(config: dict) -> dict[str, list[str]]:
    """Extract hook commands from pre-commit config.

    Returns:
        Dict mapping hook ID to full command (entry + args)
    """
    commands = {}

    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            hook_id = hook["id"]
            entry = hook.get("entry", "").split()
            args = hook.get("args", [])

            # Combine entry and args
            full_command = entry + args
            commands[hook_id] = full_command

    return commands


def compare_commands() -> dict[str, dict]:
    """Compare commands between .pre-commit-config.yaml and tool_commands.py.

    Returns:
        Dict mapping hook names to comparison results
    """
    precommit_config = load_precommit_config()
    precommit_commands = extract_precommit_commands(precommit_config)

    results = {}

    # Compare each tool command
    for tool_name, tool_command in TOOL_COMMANDS.items():
        precommit_command = precommit_commands.get(tool_name)

        if precommit_command is None:
            # Tool only in tool_commands.py (could be a custom tool)
            results[tool_name] = {
                "status": "tool_commands_only",
                "tool_command": tool_command,
                "precommit_command": None,
                "match": None,
            }
            continue

        # Normalize commands for comparison
        # tool_commands.py includes "uv run" prefix, pre-commit might not
        tool_normalized = tool_command.copy()
        precommit_normalized = precommit_command.copy()

        # Check if commands match (allowing for uv run prefix differences)
        match = False

        # Direct match
        if tool_normalized == precommit_normalized:
            match = True
        # Match if pre-commit has extra/different prefix
        elif " ".join(tool_normalized[2:]) == " ".join(precommit_normalized):
            match = True
        # Match if commands are equivalent (same tool, same args)
        elif (
            len(tool_normalized) >= 3
            and precommit_normalized
            and tool_normalized[2] == precommit_normalized[0]  # Same tool name
        ):
            # Check if args match (allowing for ordering differences)
            tool_args = set(tool_normalized[3:])
            precommit_args = set(precommit_normalized[1:])
            if tool_args == precommit_args:
                match = True

        results[tool_name] = {
            "status": "match" if match else "mismatch",
            "tool_command": tool_command,
            "precommit_command": precommit_command,
            "match": match,
        }

    # Check for hooks only in .pre-commit-config.yaml
    for hook_id in precommit_commands:
        if hook_id not in TOOL_COMMANDS:
            results[hook_id] = {
                "status": "precommit_only",
                "tool_command": None,
                "precommit_command": precommit_commands[hook_id],
                "match": None,
            }

    return results


def generate_summary_section(results: dict[str, dict], lines: list[str]) -> None:
    """Generate the summary section of the report."""
    matches = sum(1 for r in results.values() if r["status"] == "match")
    mismatches = sum(1 for r in results.values() if r["status"] == "mismatch")
    tool_only = sum(1 for r in results.values() if r["status"] == "tool_commands_only")
    precommit_only = sum(1 for r in results.values() if r["status"] == "precommit_only")

    lines.extend(
        [
            "## Summary",
            "",
            f"- ✅ Matching Commands: {matches}",
            f"- ⚠️ Mismatched Commands: {mismatches}",
            f"- 📝 tool_commands.py Only: {tool_only}",
            f"- 📝 .pre-commit-config.yaml Only: {precommit_only}",
            "",
        ]
    )


def generate_mismatched_commands_section(
    results: dict[str, dict], lines: list[str]
) -> None:
    """Generate the mismatched commands section of the report."""
    mismatches = sum(1 for r in results.values() if r["status"] == "mismatch")

    if mismatches > 0:
        lines.extend(
            [
                "## ⚠️ Mismatched Commands",
                "",
                "These hooks have different commands in the two locations:",
                "",
            ]
        )

        for tool_name, result in sorted(results.items()):
            if result["status"] != "mismatch":
                continue

            lines.extend(
                [
                    f"### `{tool_name}`",
                    "",
                    "**tool_commands.py:**",
                    "```python",
                    str(result["tool_command"]),
                    "```",
                    "",
                    "**.pre-commit-config.yaml:**",
                    "```yaml",
                    str(result["precommit_command"]),
                    "```",
                    "",
                ]
            )


def generate_tool_only_section(results: dict[str, dict], lines: list[str]) -> None:
    """Generate the tool_commands.py only section of the report."""
    tool_only = sum(1 for r in results.values() if r["status"] == "tool_commands_only")

    if tool_only > 0:
        lines.extend(
            [
                "## 📝 tool_commands.py Only",
                "",
                "These tools are defined in tool_commands.py but not .pre-commit-config.yaml:",
                "",
            ]
        )

        for tool_name, result in sorted(results.items()):
            if result["status"] != "tool_commands_only":
                continue

            lines.append(f"- **{tool_name}**: `{' '.join(result['tool_command'])}`")

        lines.append("")


def generate_precommit_only_section(results: dict[str, dict], lines: list[str]) -> None:
    """Generate the .pre-commit-config.yaml only section of the report."""
    precommit_only = sum(1 for r in results.values() if r["status"] == "precommit_only")

    if precommit_only > 0:
        lines.extend(
            [
                "## 📝 .pre-commit-config.yaml Only",
                "",
                "These hooks are in .pre-commit-config.yaml but not tool_commands.py:",
                "",
            ]
        )

        for tool_name, result in sorted(results.items()):
            if result["status"] != "precommit_only":
                continue

            lines.append(
                f"- **{tool_name}**: `{' '.join(result['precommit_command'])}`"
            )

        lines.append("")


def generate_all_consistent_section(results: dict[str, dict], lines: list[str]) -> None:
    """Generate the all commands consistent section of the report."""
    matches = sum(1 for r in results.values() if r["status"] == "match")

    if matches == len(results):
        lines.extend(
            [
                "## ✅ All Commands Consistent",
                "",
                "All hooks have matching commands between .pre-commit-config.yaml and tool_commands.py!",
                "",
            ]
        )


def generate_report(results: dict[str, dict]) -> str:
    """Generate markdown report of command consistency audit.

    Args:
        results: Comparison results from compare_commands()

    Returns:
        Markdown-formatted report
    """
    lines = [
        "# Hook Command Consistency Audit",
        "",
        "**Generated by:** `scripts/audit_command_consistency.py`",
        "**Purpose:** Ensure `.pre-commit-config.yaml` and `tool_commands.py` are consistent",
        "",
    ]

    generate_summary_section(results, lines)
    generate_mismatched_commands_section(results, lines)
    generate_tool_only_section(results, lines)
    generate_precommit_only_section(results, lines)
    generate_all_consistent_section(results, lines)

    return "\n".join(lines)


def main():
    """Main entry point."""
    print("=" * 80)
    print("Phase 10.4.2: Hook Command Consistency Audit")
    print("=" * 80)
    print()

    # Compare commands
    results = compare_commands()

    # Generate report
    report = generate_report(results)

    # Save report
    report_path = project_root / "docs" / "HOOK-COMMAND-AUDIT.md"
    report_path.write_text(report)

    print("=" * 80)
    print(f"✅ Report saved to: {report_path}")
    print("=" * 80)
    print()
    print(report)

    # Exit with error if mismatches found
    mismatches = sum(1 for r in results.values() if r["status"] == "mismatch")
    if mismatches > 0:
        print(f"\n⚠️ Found {mismatches} mismatched commands!")
        sys.exit(1)


if __name__ == "__main__":
    main()

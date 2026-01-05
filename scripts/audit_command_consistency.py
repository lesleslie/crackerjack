import sys
from pathlib import Path

import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crackerjack.config.tool_commands import TOOL_COMMANDS


def load_precommit_config() -> dict:
    config_path = project_root / ".pre-commit-config.yaml"
    with config_path.open() as f:
        return yaml.safe_load(f)


def extract_precommit_commands(config: dict) -> dict[str, list[str]]:
    commands = {}

    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            hook_id = hook["id"]
            entry = hook.get("entry", "").split()
            args = hook.get("args", [])

            full_command = entry + args
            commands[hook_id] = full_command

    return commands


def compare_commands() -> dict[str, dict]:
    precommit_config = load_precommit_config()
    precommit_commands = extract_precommit_commands(precommit_config)

    results = _compare_tool_commands(precommit_commands)
    _add_precommit_only_commands(results, precommit_commands)

    return results


def _compare_tool_commands(precommit_commands: dict[str, list[str]]) -> dict[str, dict]:
    results = {}

    for tool_name, tool_command in TOOL_COMMANDS.items():
        precommit_command = precommit_commands.get(tool_name)

        if precommit_command is None:
            results[tool_name] = _create_tool_only_result(tool_command)
            continue

        match = _commands_match(tool_command, precommit_command)
        results[tool_name] = _create_comparison_result(
            tool_command, precommit_command, match
        )

    return results


def _create_tool_only_result(tool_command: list[str]) -> dict[str, t.Any]:
    return {
        "status": "tool_commands_only",
        "tool_command": tool_command,
        "precommit_command": None,
        "match": None,
    }


def _commands_match(tool_command: list[str], precommit_command: list[str]) -> bool:
    if tool_command == precommit_command:
        return True

    if " ".join(tool_command[2:]) == " ".join(precommit_command):
        return True

    return _commands_equivalent(tool_command, precommit_command)


def _commands_equivalent(tool_command: list[str], precommit_command: list[str]) -> bool:
    if not (len(tool_command) >= 3 and precommit_command):
        return False

    if tool_command[2] != precommit_command[0]:
        return False

    tool_args = set(tool_command[3:])
    precommit_args = set(precommit_command[1:])
    return tool_args == precommit_args


def _create_comparison_result(
    tool_command: list[str], precommit_command: list[str], match: bool
) -> dict[str, t.Any]:
    return {
        "status": "match" if match else "mismatch",
        "tool_command": tool_command,
        "precommit_command": precommit_command,
        "match": match,
    }


def _add_precommit_only_commands(
    results: dict[str, dict], precommit_commands: dict[str, list[str]]
) -> None:
    for hook_id in precommit_commands:
        if hook_id not in TOOL_COMMANDS:
            results[hook_id] = {
                "status": "precommit_only",
                "tool_command": None,
                "precommit_command": precommit_commands[hook_id],
                "match": None,
            }


def generate_summary_section(results: dict[str, dict], lines: list[str]) -> None:
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
    print("=" * 80)
    print("Phase 10.4.2: Hook Command Consistency Audit")
    print("=" * 80)
    print()

    results = compare_commands()

    report = generate_report(results)

    report_path = project_root / "docs" / "HOOK-COMMAND-AUDIT.md"
    report_path.write_text(report)

    print("=" * 80)
    print(f"✅ Report saved to: {report_path}")
    print("=" * 80)
    print()
    print(report)

    mismatches = sum(1 for r in results.values() if r["status"] == "mismatch")
    if mismatches > 0:
        print(f"\n⚠️ Found {mismatches} mismatched commands!")
        sys.exit(1)


if __name__ == "__main__":
    main()

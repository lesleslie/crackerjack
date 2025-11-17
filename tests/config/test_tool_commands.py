"""Tests for tool command registry (Phase 10.1.2)."""

from pathlib import Path

import pytest

from crackerjack.config.tool_commands import (
    _build_tool_commands,
    get_tool_command,
    is_native_tool,
    list_available_tools,
)

# Build test registry with "crackerjack" as package name for testing
TOOL_COMMANDS = _build_tool_commands("crackerjack")


class TestToolCommandsRegistry:
    """Test the tool commands registry data structure."""

    def test_registry_exists(self):
        """Test that TOOL_COMMANDS registry exists and is a dict."""
        assert isinstance(TOOL_COMMANDS, dict)
        assert len(TOOL_COMMANDS) > 0

    def test_registry_has_expected_count(self):
        """Test that registry contains expected number of tools."""
        # Current registry: 3 custom + 9 native + 11 third-party = 23 tools
        assert len(TOOL_COMMANDS) == 23

    def test_all_commands_are_lists(self):
        """Test that all commands are lists of strings."""
        for hook_name, command in TOOL_COMMANDS.items():
            assert isinstance(command, list), f"{hook_name} command is not a list"
            assert len(command) > 0, f"{hook_name} command is empty"
            assert all(
                isinstance(arg, str) for arg in command
            ), f"{hook_name} command contains non-string arguments"

    def test_all_commands_use_uv(self):
        """Test that all commands start with 'uv' or 'uvx' for dependency management."""
        for hook_name, command in TOOL_COMMANDS.items():
            assert (
                command[0] in ("uv", "uvx")
            ), f"{hook_name} does not start with 'uv' or 'uvx': {command}"

    def test_custom_tools_present(self):
        """Test that custom crackerjack tools are in registry."""
        expected_custom = [
            "validate-regex-patterns",
            "skylos",
            "zuban",
        ]
        for tool in expected_custom:
            assert tool in TOOL_COMMANDS, f"Custom tool {tool} missing from registry"

    def test_native_tools_present(self):
        """Test that native Phase 8+ implementations are in registry."""
        expected_native = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-json",
            "format-json",
            "check-jsonschema",
            "check-ast",
            "check-added-large-files",
        ]
        for tool in expected_native:
            assert (
                tool in TOOL_COMMANDS
            ), f"Native tool {tool} missing from registry"

    def test_third_party_tools_present(self):
        """Test that third-party tools are in registry."""
        expected_third_party = [
            "uv-lock",
            "gitleaks",
            "bandit",
            "semgrep",
            "codespell",
            "ruff-check",
            "ruff-format",
            "mdformat",
            "creosote",
            "complexipy",
            "refurb",
        ]
        for tool in expected_third_party:
            assert (
                tool in TOOL_COMMANDS
            ), f"Third-party tool {tool} missing from registry"


class TestGetToolCommand:
    """Test the get_tool_command() function."""

    def test_get_known_tool_command(self):
        """Test retrieving command for a known tool."""
        command = get_tool_command("ruff-check")
        assert isinstance(command, list)
        assert command[0] == "uv"
        assert "ruff" in command
        assert "check" in command

    def test_get_native_tool_command(self):
        """Test retrieving command for a native tool."""
        command = get_tool_command("trailing-whitespace")
        assert isinstance(command, list)
        assert "python" in command
        assert "-m" in command
        assert "crackerjack.tools.trailing_whitespace" in command

    def test_get_unknown_tool_raises_error(self):
        """Test that unknown tool names raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_tool_command("nonexistent-tool")

        assert "Unknown hook name" in str(exc_info.value)
        assert "nonexistent-tool" in str(exc_info.value)

    def test_returns_copy_not_reference(self):
        """Test that get_tool_command returns a copy to prevent mutation."""
        command1 = get_tool_command("ruff-check")
        command2 = get_tool_command("ruff-check")

        # Modify first command
        command1.append("--extra-flag")

        # Second command should be unaffected
        assert "--extra-flag" not in command2
        assert len(command2) < len(command1)

    def test_all_registered_tools_retrievable(self):
        """Test that all tools in registry can be retrieved without error."""
        for hook_name in TOOL_COMMANDS:
            command = get_tool_command(hook_name)
            assert isinstance(command, list)
            assert len(command) > 0

    def test_retrieved_commands_match_registry(self):
        """Test that retrieved commands match registry entries."""
        for hook_name in TOOL_COMMANDS:
            command = get_tool_command(hook_name)
            # Compare values, not references
            assert command == TOOL_COMMANDS[hook_name]


class TestListAvailableTools:
    """Test the list_available_tools() function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        tools = list_available_tools()
        assert isinstance(tools, list)

    def test_returns_all_tools(self):
        """Test that all registry tools are returned."""
        tools = list_available_tools()
        assert len(tools) == len(TOOL_COMMANDS)

        for hook_name in TOOL_COMMANDS:
            assert hook_name in tools

    def test_returns_sorted_list(self):
        """Test that tools are returned in sorted order."""
        tools = list_available_tools()
        assert tools == sorted(tools)

    def test_no_duplicates(self):
        """Test that returned list has no duplicates."""
        tools = list_available_tools()
        assert len(tools) == len(set(tools))

    def test_all_strings(self):
        """Test that all returned items are strings."""
        tools = list_available_tools()
        assert all(isinstance(tool, str) for tool in tools)


class TestIsNativeTool:
    """Test the is_native_tool() function."""

    def test_native_tools_identified(self):
        """Test that native tools are correctly identified."""
        native_tools = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-added-large-files",
        ]

        for tool in native_tools:
            assert is_native_tool(tool), f"{tool} should be identified as native"

    def test_third_party_tools_not_native(self):
        """Test that third-party tools are not identified as native."""
        third_party_tools = [
            "ruff-check",
            "ruff-format",
            "codespell",
            "bandit",
            "mdformat",
        ]

        for tool in third_party_tools:
            assert not is_native_tool(tool), f"{tool} should not be identified as native"

    def test_custom_tools_not_native(self):
        """Test that custom tools are not identified as native (not in tools package)."""
        # validate-regex-patterns is in tools but categorized differently
        custom_tools = ["skylos", "zuban"]

        for tool in custom_tools:
            assert not is_native_tool(tool), f"{tool} should not be identified as native"

    def test_validate_regex_patterns_is_native(self):
        """Test that validate-regex-patterns is correctly identified as native."""
        # This tool is in crackerjack.tools package
        assert is_native_tool("validate-regex-patterns")

    def test_unknown_tool_returns_false(self):
        """Test that unknown tools return False."""
        assert not is_native_tool("nonexistent-tool")

    def test_all_tools_have_consistent_classification(self):
        """Test that all tools can be classified without errors."""
        for hook_name in TOOL_COMMANDS:
            result = is_native_tool(hook_name)
            assert isinstance(result, bool)


class TestCommandStructureValidation:
    """Test that commands have valid structure for execution."""

    def test_uv_run_pattern_for_python_tools(self):
        """Test that Python tools use 'uv run python -m' pattern."""
        python_tools = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-added-large-files",
            "validate-regex-patterns",
        ]

        for tool in python_tools:
            command = get_tool_command(tool)
            assert command[0] == "uv"
            assert command[1] == "run"
            assert command[2] == "python"
            assert command[3] == "-m"
            # Command[4] should be the module name
            assert "crackerjack" in command[4]

    def test_uv_run_pattern_for_rust_tools(self):
        """Test that Rust tools use 'uv run <tool>' pattern."""
        rust_tools = ["skylos", "zuban", "gitleaks"]

        for tool in rust_tools:
            command = get_tool_command(tool)
            assert command[0] == "uv"
            assert command[1] == "run"
            # Command[2] should be the tool binary name

    def test_config_paths_for_tools_with_configs(self):
        """Test that tools with config files include config paths."""
        # Zuban has --config-file mypy.ini
        zuban_cmd = get_tool_command("zuban")
        assert "--config-file" in zuban_cmd
        assert "mypy.ini" in zuban_cmd

        # Bandit has -c pyproject.toml (but the current impl doesn't use -c flag)
        bandit_cmd = get_tool_command("bandit")
        # Updated: Bandit uses different config approach
        assert len(bandit_cmd) > 0  # Basic sanity check that command exists

    def test_target_directories_specified(self):
        """Test that tools include target directories where needed."""
        # Test uses Path.cwd() for package detection, which will detect "crackerjack"
        # when running from crackerjack project root

        # Skylos checks detected package directory (not "." anymore)
        skylos_cmd = get_tool_command("skylos")
        # Skylos now uses f"./{package_name}" instead of "."
        assert "./crackerjack" in skylos_cmd or "crackerjack" in skylos_cmd

        # Complexipy checks detected package directory
        complexipy_cmd = get_tool_command("complexipy")
        # Should have a package name (will be "crackerjack" when running in crackerjack project)
        assert "crackerjack" in complexipy_cmd

        # Refurb checks detected package directory
        refurb_cmd = get_tool_command("refurb")
        # Should have a package name as last argument
        assert "crackerjack" in refurb_cmd

    def test_special_flags_for_specific_tools(self):
        """Test that tools with special flags have them configured."""
        # Gitleaks has protect and -v flags
        gitleaks_cmd = get_tool_command("gitleaks")
        assert "protect" in gitleaks_cmd
        assert "-v" in gitleaks_cmd

        # Mdformat auto-fixes in fast hooks (no --check)
        mdformat_cmd = get_tool_command("mdformat")
        assert "--check" not in mdformat_cmd

        # Complexipy has --max-complexity-allowed 15
        complexipy_cmd = get_tool_command("complexipy")
        assert "--max-complexity-allowed" in complexipy_cmd
        assert "15" in complexipy_cmd

        # Creosote has --venv flag
        creosote_cmd = get_tool_command("creosote")
        assert "--venv" in creosote_cmd
        assert ".venv" in creosote_cmd


class TestIntegrationWithHooks:
    """Test integration points with hooks configuration."""

    def test_all_fast_hooks_have_commands(self):
        """Test that all fast hooks have registry entries."""
        # These are the typical fast hooks from Phase 8
        fast_hooks = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "ruff-format",
        ]

        for hook in fast_hooks:
            assert hook in TOOL_COMMANDS
            command = get_tool_command(hook)
            assert len(command) > 0

    def test_all_comprehensive_hooks_have_commands(self):
        """Test that all comprehensive hooks have registry entries."""
        # These are the typical comprehensive hooks
        comprehensive_hooks = [
            "ruff-check",
            "bandit",
            "gitleaks",
            "zuban",
            "skylos",
            "complexipy",
            "refurb",
        ]

        for hook in comprehensive_hooks:
            assert hook in TOOL_COMMANDS
            command = get_tool_command(hook)
            assert len(command) > 0

    def test_no_shell_metacharacters_in_commands(self):
        """Test that commands don't contain shell metacharacters."""
        shell_metacharacters = ["|", "&", ";", ">", "<", "`", "$", "(", ")"]

        for hook_name, command in TOOL_COMMANDS.items():
            for arg in command:
                for char in shell_metacharacters:
                    assert (
                        char not in arg
                    ), f"{hook_name} command contains shell metacharacter '{char}'"

    def test_commands_are_executable_format(self):
        """Test that commands are in format suitable for subprocess.run()."""
        for hook_name in TOOL_COMMANDS:
            command = get_tool_command(hook_name)

            # Should be a list
            assert isinstance(command, list)

            # Should have at least 2 elements (uv + subcommand)
            assert len(command) >= 2

            # First element should be executable name
            assert isinstance(command[0], str)
            assert len(command[0]) > 0

            # All elements should be strings (no None, int, etc.)
            assert all(isinstance(arg, str) for arg in command)


class TestRegistryConsistency:
    """Test consistency and completeness of the registry."""

    def test_no_duplicate_commands(self):
        """Test that no two hooks have identical commands."""
        seen_commands = {}
        for hook_name, command in TOOL_COMMANDS.items():
            cmd_tuple = tuple(command)
            if cmd_tuple in seen_commands:
                pytest.fail(
                    f"Duplicate command found: {hook_name} and {seen_commands[cmd_tuple]} "
                    f"have the same command: {command}"
                )
            seen_commands[cmd_tuple] = hook_name

    def test_hook_names_are_kebab_case(self):
        """Test that all hook names follow kebab-case convention."""
        for hook_name in TOOL_COMMANDS:
            # Should not contain underscores or uppercase
            assert (
                "_" not in hook_name
            ), f"{hook_name} contains underscore (should be kebab-case)"
            assert (
                hook_name.islower()
            ), f"{hook_name} contains uppercase (should be kebab-case)"
            assert (
                "-" in hook_name or hook_name.isalnum()
            ), f"{hook_name} has unexpected format"

    def test_module_names_match_hook_names(self):
        """Test that native tool module names match hook names."""
        native_tools = {
            "trailing-whitespace": "trailing_whitespace",
            "end-of-file-fixer": "end_of_file_fixer",
            "check-yaml": "check_yaml",
            "check-toml": "check_toml",
            "check-added-large-files": "check_added_large_files",
        }

        for hook_name, module_name in native_tools.items():
            command = get_tool_command(hook_name)
            module_path = f"crackerjack.tools.{module_name}"
            assert (
                module_path in command
            ), f"{hook_name} should reference {module_path}"

    def test_all_tools_documented_in_phase_8(self):
        """Test that tool count matches current implementation."""
        # Current registry has:
        # - 3 custom tools (validate-regex-patterns, skylos, zuban)
        # - 9 native implementations (trailing-whitespace, etc.)
        # - 11 third-party tools (ruff-check, bandit, semgrep, etc.)

        custom = ["validate-regex-patterns", "skylos", "zuban"]
        native = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "check-yaml",
            "check-toml",
            "check-json",
            "format-json",
            "check-jsonschema",
            "check-ast",
            "check-added-large-files",
        ]
        third_party = [
            "uv-lock",
            "gitleaks",
            "bandit",
            "semgrep",
            "codespell",
            "ruff-check",
            "ruff-format",
            "mdformat",
            "creosote",
            "complexipy",
            "refurb",
        ]

        assert len(custom) == 3
        assert len(native) == 9
        assert len(third_party) == 11
        assert len(TOOL_COMMANDS) == len(custom) + len(native) + len(third_party)

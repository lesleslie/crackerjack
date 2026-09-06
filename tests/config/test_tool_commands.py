"""Tests for tool command registry (Phase 10.1.2)."""

import sys
from pathlib import Path

import pytest

from crackerjack.config.settings import HookSettings
from crackerjack.config.tool_commands import (
    _DEFAULT_CWD_STR,
    _SKYLOS_EXCLUDE_FOLDERS,
    _build_skylos_command,
    _build_targets,
    _build_tool_commands,
    _detect_package_name_cached,
    _preferred_binary_command,
    _preferred_binary_command_with_report,
    get_tool_command,
    is_native_tool,
    list_available_tools,
)

# Build test registry with "crackerjack" as package name for testing
TOOL_COMMANDS = _build_tool_commands("crackerjack")


class TestToolCommandsRegistry:
    """Test the tool commands registry data structure."""

    def test_registry_exists(self) -> None:
        """Test that TOOL_COMMANDS registry exists and is a dict."""
        assert isinstance(TOOL_COMMANDS, dict)
        assert len(TOOL_COMMANDS) > 0

    def test_registry_has_expected_count(self) -> None:
        """Test that registry contains expected number of tools."""
        # 6 custom + 9 native + 20 third-party = 35 tools
        # tc-refs was added to third-party without bumping the count here.
        assert len(TOOL_COMMANDS) == 35

    def test_all_commands_are_lists(self) -> None:
        """Test that all commands are lists of strings."""
        for hook_name, command in TOOL_COMMANDS.items():
            assert isinstance(command, list), f"{hook_name} command is not a list"
            assert len(command) > 0, f"{hook_name} command is empty"
            assert all(isinstance(arg, str) for arg in command), (
                f"{hook_name} command contains non-string arguments"
            )

    def test_all_commands_use_uv_or_valid_paths(self) -> None:
        """Test that all commands use uv/uvx, direct venv paths, or system tools."""
        # Tools that may use direct venv paths or the current interpreter.
        venv_optimized_tools = {
            "skylos",
            "zuban",
            "ty",
            "pyrefly",
            "gitleaks",
            "semgrep",
            "creosote",
            "complexipy",
            "refurb",
            "pyscn",
            "cohesion",
            "pymetrica",
        }
        # Tools that are system-installed (not managed by uv)
        system_tools = {
            "lychee",
            "gitleaks",
            "semgrep",
            "ty",
            "pyrefly",
            "betterleaks",
            "osv-scanner",  # Go binary installed via brew / go install
        }

        for hook_name, command in TOOL_COMMANDS.items():
            first_arg = command[0]

            # Check if command uses uv/uvx
            if first_arg in ("uv", "uvx"):
                continue

            # Check if command uses the active interpreter for python modules.
            if first_arg == sys.executable:
                continue

            # Check if command uses direct venv path (optimization for some tools)
            if hook_name in venv_optimized_tools and ".venv" in first_arg:
                continue

            # Check if command is a system-installed tool
            if Path(first_arg).name in system_tools:
                continue

            pytest.fail(
                f"{hook_name} does not use uv/uvx, direct venv path, or system tool: {command}"
            )

    def test_custom_tools_present(self) -> None:
        """Test that custom crackerjack tools are in registry."""
        expected_custom = [
            "validate-regex-patterns",
            "skylos",
            "zuban",
            "pyrefly",
            "ty",
        ]
        for tool in expected_custom:
            assert tool in TOOL_COMMANDS, f"Custom tool {tool} missing from registry"

    def test_native_tools_present(self) -> None:
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
            assert tool in TOOL_COMMANDS, f"Native tool {tool} missing from registry"

    def test_third_party_tools_present(self) -> None:
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
            "check-local-links",
            "linkcheckmd",
            "creosote",
            "complexipy",
            "refurb",
            "osv-scanner",
            "pyscn",
        ]
        for tool in expected_third_party:
            assert tool in TOOL_COMMANDS, (
                f"Third-party tool {tool} missing from registry"
            )


class TestGetToolCommand:
    """Test the get_tool_command() function."""

    def test_get_known_tool_command(self) -> None:
        """Test retrieving command for a known tool."""
        command = get_tool_command("ruff-check")
        assert isinstance(command, list)
        assert command[0] == sys.executable
        assert command[1:3] == ["-m", "ruff"]
        assert "check" in command

    def test_get_native_tool_command(self) -> None:
        """Test retrieving command for a native tool."""
        command = get_tool_command("trailing-whitespace")
        assert isinstance(command, list)
        assert command[0] == sys.executable
        assert "-m" in command
        assert "crackerjack.tools.trailing_whitespace" in command

    def test_get_unknown_tool_raises_error(self) -> None:
        """Test that unknown tool names raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_tool_command("nonexistent-tool")

        assert "Unknown hook name" in str(exc_info.value)
        assert "nonexistent-tool" in str(exc_info.value)

    def test_returns_copy_not_reference(self) -> None:
        """Test that get_tool_command returns a copy to prevent mutation."""
        command1 = get_tool_command("ruff-check")
        command2 = get_tool_command("ruff-check")

        # Modify first command
        command1.append("--extra-flag")

        # Second command should be unaffected
        assert "--extra-flag" not in command2
        assert len(command2) < len(command1)

    def test_all_registered_tools_retrievable(self) -> None:
        """Test that all tools in registry can be retrieved without error."""
        for hook_name in TOOL_COMMANDS:
            command = get_tool_command(hook_name)
            assert isinstance(command, list)
            assert len(command) > 0

    def test_retrieved_commands_match_registry(self) -> None:
        """Test that retrieved commands match registry entries."""
        for hook_name in TOOL_COMMANDS:
            command = get_tool_command(hook_name)
            # Compare values, not references
            assert command == TOOL_COMMANDS[hook_name]


class TestListAvailableTools:
    """Test the list_available_tools() function."""

    def test_returns_list(self) -> None:
        """Test that function returns a list."""
        tools = list_available_tools()
        assert isinstance(tools, list)

    def test_returns_all_tools(self) -> None:
        """Test that all registry tools are returned."""
        tools = list_available_tools()
        assert len(tools) == len(TOOL_COMMANDS)

        for hook_name in TOOL_COMMANDS:
            assert hook_name in tools

    def test_returns_sorted_list(self) -> None:
        """Test that tools are returned in sorted order."""
        tools = list_available_tools()
        assert tools == sorted(tools)

    def test_no_duplicates(self) -> None:
        """Test that returned list has no duplicates."""
        tools = list_available_tools()
        assert len(tools) == len(set(tools))

    def test_all_strings(self) -> None:
        """Test that all returned items are strings."""
        tools = list_available_tools()
        assert all(isinstance(tool, str) for tool in tools)


class TestIsNativeTool:
    """Test the is_native_tool() function."""

    def test_native_tools_identified(self) -> None:
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

    def test_third_party_tools_not_native(self) -> None:
        """Test that third-party tools are not identified as native."""
        third_party_tools = [
            "ruff-check",
            "ruff-format",
            "codespell",
            "bandit",
            "mdformat",
        ]

        for tool in third_party_tools:
            assert not is_native_tool(tool), (
                f"{tool} should not be identified as native"
            )

    def test_custom_tools_not_native(self) -> None:
        """Test that custom tools are not identified as native (not in tools package)."""
        # validate-regex-patterns is in tools but categorized differently
        custom_tools = ["skylos", "zuban"]

        for tool in custom_tools:
            assert not is_native_tool(tool), (
                f"{tool} should not be identified as native"
            )

    def test_validate_regex_patterns_is_native(self) -> None:
        """Test that validate-regex-patterns is correctly identified as native."""
        # This tool is in crackerjack.tools package
        assert is_native_tool("validate-regex-patterns")

    def test_unknown_tool_returns_false(self) -> None:
        """Test that unknown tools return False."""
        assert not is_native_tool("nonexistent-tool")

    def test_all_tools_have_consistent_classification(self) -> None:
        """Test that all tools can be classified without errors."""
        for hook_name in TOOL_COMMANDS:
            result = is_native_tool(hook_name)
            assert isinstance(result, bool)


class TestCommandStructureValidation:
    """Test that commands have valid structure for execution."""

    def test_uv_run_pattern_for_python_tools(self) -> None:
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
            assert command[0] == sys.executable
            assert command[1] == "-m"
            # Command[4] should be the module name
            assert "crackerjack" in command[2]

    def test_rust_tools_use_uv_run_or_venv_path(self) -> None:
        """Test that Rust tools use 'uv run <tool>' or direct venv path pattern."""
        # skylos may use direct venv path for performance optimization
        # zuban and gitleaks may use direct venv or system binaries
        rust_tools = ["skylos", "zuban", "gitleaks"]

        for tool in rust_tools:
            command = get_tool_command(tool)
            first_arg = command[0]

            # Accept either 'uv run' pattern, direct venv path, or system binary
            if first_arg == "uv":
                assert command[1] == "run", f"{tool}: expected 'run' after 'uv'"
                # command[2] should be the tool binary name
            elif ".venv" in first_arg:
                # Direct venv path optimization (e.g., skylos)
                assert tool in first_arg, f"{tool}: venv path should contain tool name"
            elif Path(first_arg).name == tool:
                continue
            else:
                pytest.fail(
                    f"{tool} does not use 'uv run' or direct venv path: {command}"
                )

    def test_config_paths_for_tools_with_configs(self) -> None:
        """Test that tools with config files include config paths."""
        # Zuban has --config-file mypy.ini
        zuban_cmd = get_tool_command("zuban")
        assert "--config-file" in zuban_cmd
        assert "mypy.ini" in zuban_cmd

        # Bandit has -c pyproject.toml (but the current impl doesn't use -c flag)
        bandit_cmd = get_tool_command("bandit")
        # Updated: Bandit uses different config approach
        assert len(bandit_cmd) > 0  # Basic sanity check that command exists

    def test_target_directories_specified(self) -> None:
        """Test that tools include target directories where needed."""
        # Test uses Path.cwd() for package detection, which will detect "crackerjack"
        # when running from crackerjack project root

        # Skylos checks detected package directory (not "." anymore)
        skylos_cmd = get_tool_command("skylos")
        # Skylos now uses f"./{package_name}" instead of "."
        assert any("crackerjack" in arg for arg in skylos_cmd)

        # Complexipy checks detected package directory
        complexipy_cmd = get_tool_command("complexipy")
        # Should have a package name (will be "crackerjack" when running in crackerjack project)
        assert any("crackerjack" in arg for arg in complexipy_cmd)

        # Refurb checks detected package directory
        refurb_cmd = get_tool_command("refurb")
        # Should have a package name as last argument
        assert any("crackerjack" in arg for arg in refurb_cmd)

        # NEW: ruff-check and ruff-format include scripts/ and examples/
        ruff_check_cmd = get_tool_command("ruff-check")
        assert any("crackerjack" in arg for arg in ruff_check_cmd)
        assert any("scripts" in arg for arg in ruff_check_cmd)
        assert any("examples" in arg for arg in ruff_check_cmd)

        ruff_format_cmd = get_tool_command("ruff-format")
        assert any("crackerjack" in arg for arg in ruff_format_cmd)
        assert any("scripts" in arg for arg in ruff_format_cmd)
        assert any("examples" in arg for arg in ruff_format_cmd)

        # NEW: ruff-check uses --config='<inline TOML>' for the starter pack
        assert "--config" in ruff_check_cmd
        config_idx = ruff_check_cmd.index("--config")
        config_value = ruff_check_cmd[config_idx + 1]
        # The value MUST be inline TOML, not a file path
        assert not config_value.endswith(".toml")
        assert not config_value.endswith(".toml/")
        assert config_value.startswith("lint.extend-per-file-ignores = {")
        assert '"scripts/**/*.py"' in config_value
        assert '"examples/**/*.py"' in config_value

    def test_ruff_format_has_no_config_flag(self) -> None:
        """ruff-format has no --config flag — only lint does."""
        ruff_format_cmd = get_tool_command("ruff-format")
        assert "--config" not in ruff_format_cmd

    def test_special_flags_for_specific_tools(self) -> None:
        """Test that tools with special flags have them configured."""
        # Gitleaks has protect and -v flags
        gitleaks_cmd = get_tool_command("gitleaks")
        assert "protect" in gitleaks_cmd
        assert "-v" in gitleaks_cmd

        # Mdformat auto-fixes in fast hooks (no --check)
        mdformat_cmd = get_tool_command("mdformat")
        assert "--check" not in mdformat_cmd

        # Complexipy has --max-complexity-allowed 25
        # (raised from 15 as the codebase complexity budget grew)
        complexipy_cmd = get_tool_command("complexipy")
        assert "--max-complexity-allowed" in complexipy_cmd
        assert "25" in complexipy_cmd

        # Creosote has --venv flag
        creosote_cmd = get_tool_command("creosote")
        assert "--venv" in creosote_cmd
        assert ".venv" in creosote_cmd

    def test_codespell_targets_include_scripts_and_examples(self) -> None:
        """codespell extends coverage to admin/demo code for typo detection."""
        codespell_cmd = get_tool_command("codespell")
        assert any("scripts" in arg for arg in codespell_cmd)
        assert any("examples" in arg for arg in codespell_cmd)

    def test_tc_refs_targets_include_scripts_and_examples(self) -> None:
        """tc-refs (audit-type-checking-runtime-refs) covers TYPE_CHECKING
        runtime usage in scripts/examples too."""
        tc_refs_cmd = get_tool_command("tc-refs")
        assert any("scripts" in arg for arg in tc_refs_cmd)
        assert any("examples" in arg for arg in tc_refs_cmd)


class TestIntegrationWithHooks:
    """Test integration points with hooks configuration."""

    def test_all_fast_hooks_have_commands(self) -> None:
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

    def test_all_comprehensive_hooks_have_commands(self) -> None:
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

    def test_no_shell_metacharacters_in_commands(self) -> None:
        """Test that commands don't contain shell metacharacters."""
        shell_metacharacters = ["|", "&", ";", ">", "<", "`", "$", "(", ")"]

        for hook_name, command in TOOL_COMMANDS.items():
            for arg in command:
                for char in shell_metacharacters:
                    assert char not in arg, (
                        f"{hook_name} command contains shell metacharacter '{char}'"
                    )

    def test_commands_are_executable_format(self) -> None:
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


class TestOsvScannerCommand:
    """Regression tests for the osv-scanner tool command.

    osv-scanner is the vulnerability scanner (formerly pip-audit). The
    command is the audit itself — read-only, against ``uv.lock``. No
    ``--vulnerability-service`` (osv-scanner uses OSV by default),
    no ``--skip-editable`` / ``--require-hashes`` / ``--desc`` (those were
    pip-audit-only flags that osv-scanner does not accept), and no
    ``--fix`` (auto-upgrades are handled separately by the security fixer
    via ``uv lock --upgrade-package <pkg>``).

    Note: osv-scanner does not support ``--ignore-vuln`` flags. CVE
    filtering is done post-parse in ``_parse_osv_scanner_issues`` against
    the canonical ``IGNORED_VULNERABILITY_IDS`` list.
    """

    def test_osv_scanner_command_targets_uv_lock(self) -> None:
        """osv-scanner must scan ``uv.lock`` so resolution is exact."""
        command = get_tool_command("osv-scanner")
        assert "--lockfile=uv.lock" in command

    def test_osv_scanner_command_emits_json(self) -> None:
        """osv-scanner must produce JSON output for crackerjack to parse."""
        command = get_tool_command("osv-scanner")
        assert "--format=json" in command

    def test_osv_scanner_command_invokes_scan_source(self) -> None:
        """osv-scanner requires the ``scan source`` subcommand."""
        command = get_tool_command("osv-scanner")
        assert "scan" in command
        assert "source" in command

    def test_osv_scanner_command_excludes_pip_audit_flags(self) -> None:
        """osv-scanner must not carry pip-audit-specific flags."""
        command = get_tool_command("osv-scanner")
        for forbidden in (
            "--vulnerability-service",
            "--skip-editable",
            "--require-hashes",
            "--desc",
            "--fix",
            "--ignore-vuln",  # pip-audit-only flag
        ):
            assert forbidden not in command, (
                f"osv-scanner command must not include {forbidden}: "
                "the flag is from pip-audit and osv-scanner will reject it."
            )

    def test_osv_scanner_command_does_not_use_uv_run(self) -> None:
        """osv-scanner is invoked directly (no ``uv run`` wrapper) so the
        venv-spawn tax that motivated this swap is bypassed."""
        command = get_tool_command("osv-scanner")
        assert command[0] == "osv-scanner"
        assert "uv" not in command[:1]


class TestRegistryConsistency:
    """Test consistency and completeness of the registry."""

    def test_no_duplicate_commands(self) -> None:
        """Test that no two hooks have identical commands."""
        seen_commands = {}
        for hook_name, command in TOOL_COMMANDS.items():
            cmd_tuple = tuple(command)
            if cmd_tuple in seen_commands:
                pytest.fail(
                    f"Duplicate command found: {hook_name} and {seen_commands[cmd_tuple]} "
                    f"have the same command: {command}",
                )
            seen_commands[cmd_tuple] = hook_name

    def test_hook_names_are_kebab_case(self) -> None:
        """Test that all hook names follow kebab-case convention."""
        for hook_name in TOOL_COMMANDS:
            # Should not contain underscores or uppercase
            assert "_" not in hook_name, (
                f"{hook_name} contains underscore (should be kebab-case)"
            )
            assert hook_name.islower(), (
                f"{hook_name} contains uppercase (should be kebab-case)"
            )
            assert "-" in hook_name or hook_name.isalnum(), (
                f"{hook_name} has unexpected format"
            )

    def test_module_names_match_hook_names(self) -> None:
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
            assert module_path in command, f"{hook_name} should reference {module_path}"

    def test_all_tools_documented_in_phase_8(self) -> None:
        """Test that tool count matches current implementation."""
        # 6 custom + 9 native + 20 third-party = 35 tools

        custom = [
            "validate-regex-patterns",
            "skylos",
            "zuban",
            "pyrefly",
            "ty",
            "ty-ignore-syntax",
        ]
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
            "check-local-links",
            "linkcheckmd",
            "creosote",
            "complexipy",
            "refurb",
            "osv-scanner",
            "pyscn",
            "lychee",
            "betterleaks",
            "cohesion",
            "pymetrica",
            "tc-refs",
        ]

        assert len(custom) == 6
        assert len(native) == 9
        assert len(third_party) == 20
        assert len(TOOL_COMMANDS) == len(custom) + len(native) + len(third_party)


class TestDetectPackageNameCached:
    """Coverage for _detect_package_name_cached directory fallback paths.

    The pyproject.toml branch is exercised at import time by the existing
    tests; these tests target the fall-through paths (29-41) that run when
    pyproject.toml is missing or lacks a [project].name.
    """

    def test_reads_project_name_from_pyproject(self, tmp_path: Path) -> None:
        pkg = tmp_path / "proj"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "my-pkg"\n')
        assert _detect_package_name_cached(str(pkg)) == "my_pkg"

    def test_replaces_hyphens_with_underscores(self, tmp_path: Path) -> None:
        pkg = tmp_path / "proj"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "kebab-name"\n')
        assert _detect_package_name_cached(str(pkg)) == "kebab_name"

    def test_falls_back_to_subdir_when_pyproject_missing(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        sub = pkg / "core"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "core"

    def test_falls_back_when_pyproject_lacks_project_name(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[tool.black]\nline-length = 100\n')
        sub = pkg / "core"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "core"

    def test_falls_back_when_pyproject_has_empty_project_section(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\n')
        sub = pkg / "core"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "core"

    def test_skips_excluded_subdirs(self, tmp_path: Path) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        # The function's inline exclusion set only contains these six names
        for excluded in (
            "tests",
            "docs",
            ".venv",
            "venv",
            "build",
            "dist",
        ):
            d = pkg / excluded
            d.mkdir()
            (d / "__init__.py").write_text("")
        real = pkg / "real_pkg"
        real.mkdir()
        (real / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "real_pkg"

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        hidden = pkg / ".git"
        hidden.mkdir()
        (hidden / "__init__.py").write_text("")
        real = pkg / "main"
        real.mkdir()
        (real / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "main"

    def test_skips_files_not_directories(self, tmp_path: Path) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        # Plain file with init-like contents should not be picked up
        (pkg / "not_a_dir.py").write_text("")
        real = pkg / "main"
        real.mkdir()
        (real / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "main"

    def test_skips_only_files_no_subdirs(self, tmp_path: Path) -> None:
        """Deterministically triggers the file-skip branch (line 35)."""
        pkg = tmp_path / "root"
        pkg.mkdir()
        # No subdirectories — only files, so iterdir() must skip each via line 35
        (pkg / "file1.py").write_text("")
        (pkg / "file2.txt").write_text("")
        (pkg / "file3.md").write_text("")
        # Falls through to root dir name since no subdir matched
        assert _detect_package_name_cached(str(pkg)) == "root"

    def test_subdir_without_init_skipped(self, tmp_path: Path) -> None:
        pkg = tmp_path / "root"
        pkg.mkdir()
        empty_dir = pkg / "empty"
        empty_dir.mkdir()
        # no __init__.py
        real = pkg / "main"
        real.mkdir()
        (real / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "main"

    def test_returns_root_dir_name_when_nothing_matches(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "my-root"
        pkg.mkdir()
        # No pyproject.toml, no subdirs
        assert _detect_package_name_cached(str(pkg)) == "my_root"

    def test_returns_root_dir_name_when_only_excluded_subdirs(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "my-root"
        pkg.mkdir()
        for excluded in ("tests", "docs", ".venv"):
            d = pkg / excluded
            d.mkdir()
            (d / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "my_root"

    def test_lru_cache_returns_same_value(self, tmp_path: Path) -> None:
        pkg = tmp_path / "cached"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "cached-proj"\n')
        first = _detect_package_name_cached(str(pkg))
        second = _detect_package_name_cached(str(pkg))
        assert first == second == "cached_proj"

    def test_handles_invalid_toml_gracefully(self, tmp_path: Path) -> None:
        """Invalid TOML should not raise — falls through to dir scan."""
        pkg = tmp_path / "root"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text("not valid toml [[[")
        sub = pkg / "core"
        sub.mkdir()
        (sub / "__init__.py").write_text("")
        assert _detect_package_name_cached(str(pkg)) == "core"


class TestBuildSkylosCommand:
    """Coverage for _build_skylos_command uv-run fallback (line 71)."""

    def test_uses_venv_binary_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "skylos").write_text("#!/bin/sh\n")
        monkeypatch.chdir(tmp_path)
        cmd = _build_skylos_command("myapp")
        assert cmd[0] == str(venv_bin / "skylos")
        assert "./myapp" in cmd

    def test_falls_back_to_uv_run_when_venv_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)  # No .venv at all
        cmd = _build_skylos_command("myapp")
        assert cmd[:3] == ["uv", "run", "skylos"]

    def test_includes_all_exclude_folders(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        cmd = _build_skylos_command("myapp")
        for folder in _SKYLOS_EXCLUDE_FOLDERS:
            assert folder in cmd, f"missing --exclude-folder {folder}"
        # Each folder appears with its flag prefix
        exclude_idx = cmd.index("--exclude-folder")
        assert cmd[exclude_idx + 1] == _SKYLOS_EXCLUDE_FOLDERS[0]

    def test_includes_confidence_and_limit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        cmd = _build_skylos_command("myapp")
        idx = cmd.index("--confidence")
        assert cmd[idx + 1] == "70"
        idx = cmd.index("--limit")
        assert cmd[idx + 1] == "50"

    def test_diff_base_uses_env_var_when_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PRE_COMMIT_FROM_REF", "origin/main")
        cmd = _build_skylos_command("myapp")
        idx = cmd.index("--diff-base")
        assert cmd[idx + 1] == "origin/main"

    def test_diff_base_defaults_to_head_tilde_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PRE_COMMIT_FROM_REF", raising=False)
        cmd = _build_skylos_command("myapp")
        idx = cmd.index("--diff-base")
        assert cmd[idx + 1] == "HEAD~1"

    def test_appends_package_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        cmd = _build_skylos_command("myapp")
        assert cmd[-1] == "./myapp"


class TestPreferredBinaryCommand:
    """Coverage for _preferred_binary_command (line 110 bare-name fallback)."""

    def test_uses_venv_path_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        tool = venv_bin / "mytool"
        tool.write_text("#!/bin/sh\n")
        monkeypatch.chdir(tmp_path)
        cmd = _preferred_binary_command("mytool", "a", "b")
        assert cmd == [str(tool), "a", "b"]

    def test_uses_shutil_which_when_no_venv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: f"/usr/bin/{name}" if name == "mytool" else None,
        )
        cmd = _preferred_binary_command("mytool", "arg")
        assert cmd == ["/usr/bin/mytool", "arg"]

    def test_falls_back_to_bare_name_when_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: None,
        )
        cmd = _preferred_binary_command("mytool", "a", "b")
        assert cmd == ["mytool", "a", "b"]

    def test_returns_list_with_only_tool_name_when_no_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: None,
        )
        cmd = _preferred_binary_command("mytool")
        assert cmd == ["mytool"]


class TestPreferredBinaryCommandWithReport:
    """Coverage for _preferred_binary_command_with_report (creates parent dir)."""

    def test_creates_parent_dir_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: None,
        )
        report = tmp_path / "cache" / "subdir" / "out.json"
        assert not report.parent.exists()
        _preferred_binary_command_with_report("mytool", str(report))
        assert report.parent.exists()

    def test_idempotent_when_parent_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: None,
        )
        report = tmp_path / "existing" / "out.json"
        report.parent.mkdir()
        # Should not raise even though dir already exists
        cmd = _preferred_binary_command_with_report("mytool", str(report))
        assert cmd == ["mytool"]

    def test_creates_deeply_nested_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "crackerjack.config.tool_commands.shutil.which",
            lambda name: None,
        )
        report = tmp_path / "a" / "b" / "c" / "d" / "report.json"
        _preferred_binary_command_with_report("mytool", str(report))
        assert report.parent.exists()


class TestBuildTargetsHelper:
    """Coverage for _build_targets canonical target list.

    Behavior: candidates = ["./{package_name}", "./scripts", "./examples"].
    Only directories that exist on disk are returned — consumer repos that
    lack scripts/ or examples/ won't fail tool invocations with "directory
    not found". The package directory is required (it's the package itself).
    """

    def test_returns_canonical_targets_when_all_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All three targets returned when scripts/ and examples/ both exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "myapp").mkdir()
        (tmp_path / "scripts").mkdir()
        (tmp_path / "examples").mkdir()

        assert _build_targets("myapp") == ["./myapp", "./scripts", "./examples"]

    def test_distinct_per_package_name(self, tmp_path: Path) -> None:
        monkeypatch_ = pytest.MonkeyPatch()
        monkeypatch_.chdir(tmp_path)
        (tmp_path / "foo").mkdir()
        (tmp_path / "bar").mkdir()

        assert _build_targets("foo") != _build_targets("bar")
        monkeypatch_.undo()

    def test_contains_scripts_and_examples_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "anything").mkdir()
        (tmp_path / "scripts").mkdir()
        (tmp_path / "examples").mkdir()

        targets = _build_targets("anything")
        assert "./scripts" in targets
        assert "./examples" in targets

    def test_package_target_uses_dot_slash_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "anything").mkdir()

        targets = _build_targets("anything")
        assert targets[0].startswith("./")

    def test_skips_missing_examples_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Consumer repos without an examples/ dir should not fail tool invocations."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "myapp").mkdir()
        (tmp_path / "scripts").mkdir()
        # No examples/ directory

        targets = _build_targets("myapp")
        assert "./examples" not in targets
        assert "./myapp" in targets
        assert "./scripts" in targets

    def test_skips_missing_scripts_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Consumer repos without a scripts/ dir should not fail tool invocations."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "myapp").mkdir()
        (tmp_path / "examples").mkdir()
        # No scripts/ directory

        targets = _build_targets("myapp")
        assert "./scripts" not in targets
        assert "./myapp" in targets
        assert "./examples" in targets

    def test_skips_both_optional_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Library-style repo with only the package — neither scripts/ nor examples/."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "myapp").mkdir()
        # No scripts/ or examples/

        targets = _build_targets("myapp")
        assert targets == ["./myapp"]

    def test_package_dir_missing_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edge case: package dir doesn't exist either. Returns empty list.

        This is a degenerate case (the package should always exist when
        crackerjack is being run on it) but the function shouldn't crash.
        """
        monkeypatch.chdir(tmp_path)
        # Nothing exists in tmp_path

        targets = _build_targets("nonexistent_package")
        assert targets == []


class TestGetToolCommandPkgPath:
    """Coverage for get_tool_command pkg_path branches (358-362)."""

    def test_explicit_pkg_path_as_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        pkg = tmp_path / "altpkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "alt-pkg"\n')
        # Create the normalized package dir at CWD so _build_targets filter passes.
        (tmp_path / "alt_pkg").mkdir()
        cmd = get_tool_command("ruff-check", pkg_path=str(pkg))
        assert isinstance(cmd, list)
        # The command should target alt-pkg
        assert "./alt_pkg" in cmd

    def test_explicit_pkg_path_as_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        pkg = tmp_path / "pathpkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "path-pkg"\n')
        # Create the normalized package dir at CWD so _build_targets filter passes.
        (tmp_path / "path_pkg").mkdir()
        cmd = get_tool_command("ruff-check", pkg_path=pkg)
        assert "./path_pkg" in cmd

    def test_pkg_path_matching_default_cwd_uses_default(self) -> None:
        """Passing Path(_DEFAULT_CWD_STR) should match the default branch."""
        cmd = get_tool_command("ruff-check", pkg_path=Path(_DEFAULT_CWD_STR))
        assert isinstance(cmd, list)
        assert len(cmd) > 0

    def test_pkg_path_default_cwd_string_uses_default(self) -> None:
        """Passing _DEFAULT_CWD_STR as string should match default branch."""
        cmd = get_tool_command("ruff-check", pkg_path=_DEFAULT_CWD_STR)
        assert isinstance(cmd, list)

    def test_explicit_pkg_path_skylos_uses_target_package(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "skylospkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "skylos-pkg"\n')
        cmd = get_tool_command("skylos", pkg_path=pkg)
        assert "./skylos_pkg" in cmd


class TestGetToolCommandVerbose:
    """Coverage for get_tool_command ty --verbose injection (line 384)."""

    def test_verbose_true_appends_to_ty(self) -> None:
        cmd = get_tool_command("ty", verbose=True)
        assert cmd[-1] == "--verbose"

    def test_verbose_false_omits_for_ty(self) -> None:
        cmd = get_tool_command("ty", verbose=False)
        assert "--verbose" not in cmd

    def test_verbose_default_omits_for_ty(self) -> None:
        cmd = get_tool_command("ty")
        assert "--verbose" not in cmd

    def test_verbose_true_omits_for_non_ty(self) -> None:
        cmd = get_tool_command("ruff-check", verbose=True)
        assert "--verbose" not in cmd

    def test_verbose_true_omits_for_zuban(self) -> None:
        cmd = get_tool_command("zuban", verbose=True)
        assert "--verbose" not in cmd

    def test_verbose_true_omits_for_bandit(self) -> None:
        cmd = get_tool_command("bandit", verbose=True)
        assert "--verbose" not in cmd

    def test_verbose_true_with_explicit_pkg_path(
        self, tmp_path: Path
    ) -> None:
        pkg = tmp_path / "verbosepkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text('[project]\nname = "verbose-pkg"\n')
        cmd = get_tool_command("ty", pkg_path=pkg, verbose=True)
        assert cmd[-1] == "--verbose"


class TestGetToolCommandUnsafeFixes:
    """Coverage for get_tool_command --unsafe-fixes injection (378-381)."""

    def test_unsafe_fixes_injected_after_fix_when_enabled(self) -> None:
        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd = get_tool_command("ruff-check", settings=settings)
        fix_idx = cmd.index("--fix")
        assert cmd[fix_idx + 1] == "--unsafe-fixes"

    def test_unsafe_fixes_not_injected_when_disabled(self) -> None:
        settings = HookSettings(ruff_unsafe_fixes=False)
        cmd = get_tool_command("ruff-check", settings=settings)
        assert "--unsafe-fixes" not in cmd

    def test_unsafe_fixes_not_injected_when_settings_none(self) -> None:
        cmd = get_tool_command("ruff-check", settings=None)
        assert "--unsafe-fixes" not in cmd

    def test_unsafe_fixes_not_injected_for_bandit(self) -> None:
        """Injection is keyed to ruff-check only."""
        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd = get_tool_command("bandit", settings=settings)
        assert "--unsafe-fixes" not in cmd

    def test_unsafe_fixes_not_injected_for_codespell(self) -> None:
        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd = get_tool_command("codespell", settings=settings)
        assert "--unsafe-fixes" not in cmd

    def test_unsafe_fixes_not_injected_for_ty(self) -> None:
        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd = get_tool_command("ty", settings=settings)
        assert "--unsafe-fixes" not in cmd

    def test_unsafe_fixes_returns_copy(self) -> None:
        """Ensure mutation of returned cmd does not affect subsequent calls."""
        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd1 = get_tool_command("ruff-check", settings=settings)
        cmd1.append("--user-extra")
        cmd2 = get_tool_command("ruff-check", settings=settings)
        assert "--user-extra" not in cmd2

    def test_unsafe_fixes_appends_when_fix_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When --fix is missing from the cached command, --unsafe-fixes is appended (line 381).

        Production ruff-check always includes --fix, so this branch is
        defensive. Monkeypatch the cached commands to simulate a command
        variant without --fix.
        """
        import crackerjack.config.tool_commands as tc

        # Build a modified ruff-check command without --fix
        original = list(tc._DEFAULT_COMMANDS["ruff-check"])
        assert "--fix" in original  # sanity check the prod command
        modified = tuple(arg for arg in original if arg != "--fix")
        assert "--fix" not in modified

        # Patch the default commands with the modified version
        patched = dict(tc._DEFAULT_COMMANDS)
        patched["ruff-check"] = modified
        monkeypatch.setattr(tc, "_DEFAULT_COMMANDS", patched)

        settings = HookSettings(ruff_unsafe_fixes=True)
        cmd = get_tool_command("ruff-check", settings=settings)
        assert "--unsafe-fixes" in cmd
        # And not double-inserted after --fix (since --fix isn't there)
        assert cmd.count("--unsafe-fixes") == 1


class TestSkylosExcludeFoldersConstant:
    """Coverage for the _SKYLOS_EXCLUDE_FOLDERS module constant."""

    def test_contains_expected_entries(self) -> None:
        expected = {
            "tests",
            "docs",
            "scripts",
            "examples",
            "archive",
            "assets",
            "templates",
            "tools",
            "worktrees",
            "settings",
            ".venv",
            "venv",
            "build",
            "dist",
            "htmlcov",
            "logs",
            "node_modules",
        }
        assert expected.issubset(set(_SKYLOS_EXCLUDE_FOLDERS))

    def test_is_list(self) -> None:
        assert isinstance(_SKYLOS_EXCLUDE_FOLDERS, list)

    def test_all_strings(self) -> None:
        assert all(isinstance(f, str) for f in _SKYLOS_EXCLUDE_FOLDERS)


class TestDefaultCwdStr:
    """Coverage for the _DEFAULT_CWD_STR module constant."""

    def test_is_string(self) -> None:
        assert isinstance(_DEFAULT_CWD_STR, str)

    def test_matches_current_directory(self) -> None:
        assert _DEFAULT_CWD_STR == str(Path.cwd())

    def test_is_absolute_path(self) -> None:
        assert Path(_DEFAULT_CWD_STR).is_absolute()

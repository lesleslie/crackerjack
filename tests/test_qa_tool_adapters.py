"""Integration tests for QA tool adapters.

Tests cover RuffAdapter, BanditAdapter, GitleaksAdapter, ZubanAdapter,
RefurbAdapter, ComplexipyAdapter, CreosoteAdapter, CodespellAdapter,
and MdformatAdapter with synchronous configuration validation.
"""

from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest

from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
from crackerjack.adapters.format.mdformat import MdformatAdapter, MdformatSettings
from crackerjack.adapters.lint.codespell import CodespellAdapter, CodespellSettings
from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings
from crackerjack.adapters.security.gitleaks import GitleaksAdapter, GitleaksSettings
from crackerjack.adapters.type.zuban import ZubanAdapter, ZubanSettings
from crackerjack.adapters.refactor.refurb import RefurbAdapter, RefurbSettings
from crackerjack.adapters.refactor.creosote import CreosoteAdapter, CreosoteSettings
from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter, ComplexipySettings
from crackerjack.adapters._tool_adapter_base import BaseToolAdapter
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType


class TestRuffAdapter:
    """Tests for RuffAdapter (lint + format)."""

    def test_ruff_adapter_lint_mode(self):
        """Test RuffAdapter in lint mode."""
        settings = RuffSettings(mode="check", fix_enabled=False)
        adapter = RuffAdapter(settings=settings)

        assert adapter.settings.mode == "check"
        assert adapter.settings.fix_enabled is False
        assert isinstance(adapter.adapter_name, str)
        assert isinstance(adapter.module_id, UUID)

    def test_ruff_adapter_format_mode(self):
        """Test RuffAdapter in format mode."""
        settings = RuffSettings(mode="format", fix_enabled=True)
        adapter = RuffAdapter(settings=settings)

        assert adapter.settings.mode == "format"
        assert adapter.settings.fix_enabled is True

    def test_ruff_adapter_extends_base_tool(self):
        """Test RuffAdapter extends BaseToolAdapter."""
        adapter = RuffAdapter()
        assert isinstance(adapter, BaseToolAdapter)

    def test_ruff_adapter_tool_name(self):
        """Test RuffAdapter tool_name property."""
        adapter = RuffAdapter()
        assert adapter.tool_name == "ruff"

    def test_ruff_adapter_default_config(self):
        """Test RuffAdapter provides default configuration."""
        adapter = RuffAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.LINT
        assert isinstance(config.file_patterns, list)
        assert any("*.py" in pattern for pattern in config.file_patterns)

    def test_ruff_adapter_build_command_check_mode(self):
        """Test RuffAdapter builds correct command in check mode."""
        settings = RuffSettings(mode="check", use_json_output=True)
        adapter = RuffAdapter(settings=settings)

        files = [Path("test.py"), Path("main.py")]
        command = adapter.build_command(files, None)

        assert "ruff" in command
        assert "check" in command
        assert "--output-format" in command or "json" in command

    def test_ruff_adapter_build_command_format_mode(self):
        """Test RuffAdapter builds correct command in format mode."""
        settings = RuffSettings(mode="format", fix_enabled=False)
        adapter = RuffAdapter(settings=settings)

        files = [Path("test.py")]
        command = adapter.build_command(files, None)

        assert "ruff" in command
        assert "format" in command
        assert "--check" in command  # Check mode, don't modify


class TestBanditAdapter:
    """Tests for BanditAdapter (security)."""

    def test_bandit_adapter_initialization(self):
        """Test BanditAdapter initialization."""
        settings = BanditSettings(severity_level="high", confidence_level="high")
        adapter = BanditAdapter(settings=settings)

        assert adapter.settings.severity_level == "high"
        assert adapter.settings.confidence_level == "high"

    def test_bandit_adapter_default_config(self):
        """Test BanditAdapter default configuration."""
        adapter = BanditAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.SECURITY
        assert config.stage == "comprehensive"  # Security in comprehensive stage

    def test_bandit_adapter_tool_name(self):
        """Test BanditAdapter tool name."""
        adapter = BanditAdapter()
        assert adapter.tool_name == "bandit"

    def test_bandit_adapter_excludes_tests_by_default(self):
        """Test BanditAdapter excludes tests by default."""
        settings = BanditSettings()
        assert settings.exclude_tests is True


class TestGitleaksAdapter:
    """Tests for GitleaksAdapter (secrets detection)."""

    def test_gitleaks_adapter_detect_mode(self):
        """Test GitleaksAdapter in detect mode."""
        settings = GitleaksSettings(scan_mode="detect", redact=True)
        adapter = GitleaksAdapter(settings=settings)

        assert adapter.settings.scan_mode == "detect"
        assert adapter.settings.redact is True

    def test_gitleaks_adapter_protect_mode(self):
        """Test GitleaksAdapter in protect mode."""
        settings = GitleaksSettings(scan_mode="protect")
        adapter = GitleaksAdapter(settings=settings)

        assert adapter.settings.scan_mode == "protect"

    def test_gitleaks_adapter_default_config(self):
        """Test GitleaksAdapter default configuration."""
        adapter = GitleaksAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.SECURITY
        assert config.stage == "fast"  # Secrets detection in fast stage

    def test_gitleaks_adapter_tool_name(self):
        """Test GitleaksAdapter tool name."""
        adapter = GitleaksAdapter()
        assert adapter.tool_name == "gitleaks"


class TestZubanAdapter:
    """Tests for ZubanAdapter (type checking)."""

    def test_zuban_adapter_strict_mode(self):
        """Test ZubanAdapter with strict mode."""
        settings = ZubanSettings(strict_mode=True, incremental=True)
        adapter = ZubanAdapter(settings=settings)

        assert adapter.settings.strict_mode is True
        assert adapter.settings.incremental is True

    def test_zuban_adapter_default_config(self):
        """Test ZubanAdapter default configuration."""
        adapter = ZubanAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.TYPE
        assert config.stage == "comprehensive"  # Type checking comprehensive

    def test_zuban_adapter_tool_name(self):
        """Test ZubanAdapter tool name."""
        adapter = ZubanAdapter()
        assert adapter.tool_name == "zuban"


class TestRefurbAdapter:
    """Tests for RefurbAdapter (refactoring suggestions)."""

    def test_refurb_adapter_with_disabled_checks(self):
        """Test RefurbAdapter with specific checks disabled."""
        settings = RefurbSettings(disable_checks=["FURB101", "FURB102"])
        adapter = RefurbAdapter(settings=settings)

        assert len(adapter.settings.disable_checks) == 2
        assert "FURB101" in adapter.settings.disable_checks

    def test_refurb_adapter_default_config(self):
        """Test RefurbAdapter default configuration."""
        adapter = RefurbAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.REFACTOR
        assert config.stage == "comprehensive"

    def test_refurb_adapter_tool_name(self):
        """Test RefurbAdapter tool name."""
        adapter = RefurbAdapter()
        assert adapter.tool_name == "refurb"


class TestComplexipyAdapter:
    """Tests for ComplexipyAdapter (complexity analysis)."""

    def test_complexipy_adapter_max_complexity(self):
        """Test ComplexipyAdapter with max complexity setting."""
        settings = ComplexipySettings(
            max_complexity=15,  # Crackerjack standard
            include_cognitive=True,
        )
        adapter = ComplexipyAdapter(settings=settings)

        assert adapter.settings.max_complexity == 15
        assert adapter.settings.include_cognitive is True

    def test_complexipy_adapter_default_config(self):
        """Test ComplexipyAdapter default configuration."""
        adapter = ComplexipyAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.COMPLEXITY
        assert config.stage == "comprehensive"

    def test_complexipy_adapter_tool_name(self):
        """Test ComplexipyAdapter tool name."""
        adapter = ComplexipyAdapter()
        assert adapter.tool_name == "complexipy"


class TestCreosoteAdapter:
    """Tests for CreosoteAdapter (unused dependencies)."""

    def test_creosote_adapter_with_excludes(self):
        """Test CreosoteAdapter with excluded dependencies."""
        settings = CreosoteSettings(
            exclude_deps=["pytest", "black", "ruff"],
        )
        adapter = CreosoteAdapter(settings=settings)

        assert len(adapter.settings.exclude_deps) == 3
        assert "pytest" in adapter.settings.exclude_deps

    def test_creosote_adapter_with_paths(self):
        """Test CreosoteAdapter with custom scan paths."""
        settings = CreosoteSettings(
            paths=[Path("src"), Path("tests")],
        )
        adapter = CreosoteAdapter(settings=settings)

        assert len(adapter.settings.paths) == 2

    def test_creosote_adapter_default_config(self):
        """Test CreosoteAdapter default configuration."""
        adapter = CreosoteAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.REFACTOR
        assert config.stage == "comprehensive"

    def test_creosote_adapter_tool_name(self):
        """Test CreosoteAdapter tool name."""
        adapter = CreosoteAdapter()
        assert adapter.tool_name == "creosote"


class TestCodespellAdapter:
    """Tests for CodespellAdapter (spelling)."""

    def test_codespell_adapter_with_ignore_words(self):
        """Test CodespellAdapter with ignored words."""
        settings = CodespellSettings(
            ignore_words=["acb", "pydantic", "uuid"],
            skip_hidden=True,
        )
        adapter = CodespellAdapter(settings=settings)

        assert len(adapter.settings.ignore_words) == 3
        assert "acb" in adapter.settings.ignore_words
        assert adapter.settings.skip_hidden is True

    def test_codespell_adapter_auto_fix(self):
        """Test CodespellAdapter with auto-fix enabled."""
        settings = CodespellSettings(fix_enabled=True)
        adapter = CodespellAdapter(settings=settings)

        assert adapter.settings.fix_enabled is True

    def test_codespell_adapter_default_config(self):
        """Test CodespellAdapter default configuration."""
        adapter = CodespellAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.FORMAT
        assert config.stage == "fast"  # Spelling in fast stage

    def test_codespell_adapter_tool_name(self):
        """Test CodespellAdapter tool name."""
        adapter = CodespellAdapter()
        assert adapter.tool_name == "codespell"


class TestMdformatAdapter:
    """Tests for MdformatAdapter (markdown formatting)."""

    def test_mdformat_adapter_check_mode(self):
        """Test MdformatAdapter in check-only mode."""
        settings = MdformatSettings(
            fix_enabled=False,
            line_length=88,
        )
        adapter = MdformatAdapter(settings=settings)

        assert adapter.settings.fix_enabled is False
        assert adapter.settings.line_length == 88

    def test_mdformat_adapter_format_mode(self):
        """Test MdformatAdapter with formatting enabled."""
        settings = MdformatSettings(fix_enabled=True)
        adapter = MdformatAdapter(settings=settings)

        assert adapter.settings.fix_enabled is True

    def test_mdformat_adapter_wrap_mode(self):
        """Test MdformatAdapter wrap mode options."""
        settings = MdformatSettings(wrap_mode="keep")
        adapter = MdformatAdapter(settings=settings)

        assert adapter.settings.wrap_mode == "keep"

    def test_mdformat_adapter_default_config(self):
        """Test MdformatAdapter default configuration."""
        adapter = MdformatAdapter()
        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.check_type == QACheckType.FORMAT
        assert config.stage == "fast"  # Markdown in fast stage
        assert config.is_formatter is True

    def test_mdformat_adapter_tool_name(self):
        """Test MdformatAdapter tool name."""
        adapter = MdformatAdapter()
        assert adapter.tool_name == "mdformat"


class TestToolAdapterCommonPatterns:
    """Test common patterns across all tool adapters."""

    @pytest.fixture
    def all_adapters(self):
        """All tool adapter classes."""
        return [
            RuffAdapter,
            BanditAdapter,
            GitleaksAdapter,
            ZubanAdapter,
            RefurbAdapter,
            ComplexipyAdapter,
            CreosoteAdapter,
            CodespellAdapter,
            MdformatAdapter,
        ]

    def test_all_extend_base_tool_adapter(self, all_adapters):
        """Test all tool adapters extend BaseToolAdapter."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert isinstance(adapter, BaseToolAdapter)

    def test_all_have_tool_name(self, all_adapters):
        """Test all adapters have tool_name property."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert hasattr(adapter, "tool_name")
            assert isinstance(adapter.tool_name, str)
            assert len(adapter.tool_name) > 0

    def test_all_have_module_id(self, all_adapters):
        """Test all adapters have module_id property."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert hasattr(adapter, "module_id")
            assert isinstance(adapter.module_id, UUID)

    def test_all_have_adapter_name(self, all_adapters):
        """Test all adapters have adapter_name property."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert hasattr(adapter, "adapter_name")
            assert isinstance(adapter.adapter_name, str)
            assert len(adapter.adapter_name) > 0

    def test_all_provide_default_config(self, all_adapters):
        """Test all adapters provide default configuration."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            config = adapter.get_default_config()
            assert isinstance(config, QACheckConfig)
            assert isinstance(config.check_id, UUID)
            assert config.enabled is not None
            assert isinstance(config.file_patterns, list)

    def test_all_have_build_command_method(self, all_adapters):
        """Test all adapters have build_command method."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert hasattr(adapter, "build_command")
            assert callable(adapter.build_command)

    def test_all_have_parse_output_method(self, all_adapters):
        """Test all adapters have parse_output method."""
        for adapter_class in all_adapters:
            adapter = adapter_class()
            assert hasattr(adapter, "parse_output")
            assert callable(adapter.parse_output)


class TestToolAdapterModuleRegistration:
    """Test ACB module registration for tool adapters."""

    def test_all_modules_have_registration(self):
        """Test all adapter modules have MODULE_ID and MODULE_STATUS."""
        from crackerjack.adapters.format import ruff, mdformat
        from crackerjack.adapters.lint import codespell
        from crackerjack.adapters.sast import bandit
        from crackerjack.adapters.security import gitleaks
        from crackerjack.adapters.type import zuban
        from crackerjack.adapters.refactor import refurb, creosote
        from crackerjack.adapters.complexity import complexipy

        modules = [
            ruff,
            bandit,
            gitleaks,
            zuban,
            refurb,
            complexipy,
            creosote,
            codespell,
            mdformat,
        ]

        for module in modules:
            assert hasattr(module, "MODULE_ID")
            assert isinstance(module.MODULE_ID, UUID)
            assert hasattr(module, "MODULE_STATUS")
            assert module.MODULE_STATUS in ["stable", "beta", "experimental"]


class TestToolAdapterStageAssignment:
    """Test stage assignment for tool adapters."""

    def test_fast_stage_adapters(self):
        """Test adapters assigned to fast stage."""
        # Ruff (lint+format), Gitleaks (secrets), Codespell, Mdformat
        fast_adapters = [
            RuffAdapter,
            GitleaksAdapter,
            CodespellAdapter,
            MdformatAdapter,
        ]

        for adapter_class in fast_adapters:
            adapter = adapter_class()
            config = adapter.get_default_config()
            assert config.stage == "fast", (
                f"{adapter_class.__name__} should be in fast stage"
            )

    def test_comprehensive_stage_adapters(self):
        """Test adapters assigned to comprehensive stage."""
        # Bandit, Zuban, Refurb, Complexipy, Creosote
        comp_adapters = [
            BanditAdapter,
            ZubanAdapter,
            RefurbAdapter,
            ComplexipyAdapter,
            CreosoteAdapter,
        ]

        for adapter_class in comp_adapters:
            adapter = adapter_class()
            config = adapter.get_default_config()
            assert config.stage == "comprehensive", (
                f"{adapter_class.__name__} should be in comprehensive stage"
            )


class TestToolAdapterFilePatterns:
    """Test file pattern configuration for tool adapters."""

    def test_python_adapters_have_py_patterns(self):
        """Test Python-specific adapters have .py file patterns."""
        python_adapters = [
            RuffAdapter,
            BanditAdapter,
            ZubanAdapter,
            RefurbAdapter,
            ComplexipyAdapter,
        ]

        for adapter_class in python_adapters:
            adapter = adapter_class()
            config = adapter.get_default_config()

            patterns_str = " ".join(config.file_patterns)
            assert "*.py" in patterns_str or "**/*.py" in patterns_str, (
                f"{adapter_class.__name__} should match Python files"
            )

    def test_markdown_adapter_has_md_patterns(self):
        """Test Markdown adapter has .md file patterns."""
        adapter = MdformatAdapter()
        config = adapter.get_default_config()

        patterns_str = " ".join(config.file_patterns)
        assert "*.md" in patterns_str or "**/*.md" in patterns_str


class TestToolAdapterParallelSafety:
    """Test parallel execution safety flags."""

    def test_formatters_are_not_always_parallel_safe(self):
        """Test formatters may have parallel safety considerations."""
        # Formatters that modify files may not be parallel safe
        adapter = RuffAdapter(settings=RuffSettings(mode="format", fix_enabled=True))
        config = adapter.get_default_config()

        # Should have parallel_safe field
        assert hasattr(config, "parallel_safe")
        assert isinstance(config.parallel_safe, bool)

    def test_read_only_checks_are_parallel_safe(self):
        """Test read-only checks are marked parallel safe."""
        # Read-only checks should be parallel safe
        read_only_adapters = [
            BanditAdapter,
            ZubanAdapter,
            ComplexipyAdapter,
            CreosoteAdapter,
        ]

        for adapter_class in read_only_adapters:
            adapter = adapter_class()
            config = adapter.get_default_config()
            assert config.parallel_safe is True, (
                f"{adapter_class.__name__} should be parallel safe"
            )

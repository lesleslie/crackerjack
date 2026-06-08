"""Tests for TreeSitterAdapter (crackerjack.adapters.treesitter.treesitter).

The adapter is a tree-sitter binding wrapper. We mock the optional
``mcp_common.parsing.tree_sitter`` import at its import site so the tests
run regardless of whether the binary is installed.
"""

from __future__ import annotations

import sys
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from crackerjack.adapters.treesitter.treesitter import (
    MODULE_ID,
    TreeSitterAdapter,
    TreeSitterQualityAdapter,
    TreeSitterSettings,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class _FakeSupportedLanguage:
    PYTHON = "python"
    GO = "go"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    UNKNOWN = "unknown"


class _FakeComplexityMetrics:
    def __init__(
        self,
        cyclomatic: int = 1,
        nesting_depth: int = 0,
        num_parameters: int = 0,
        cognitive: int = 0,
        lines_of_code: int = 0,
        num_returns: int = 0,
    ) -> None:
        self.cyclomatic = cyclomatic
        self.nesting_depth = nesting_depth
        self.num_parameters = num_parameters
        self.cognitive = cognitive
        self.lines_of_code = lines_of_code
        self.num_returns = num_returns


class _FakeParseResult:
    def __init__(
        self,
        success: bool = True,
        complexity: dict[str, _FakeComplexityMetrics] | None = None,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.complexity = complexity or {}
        self.error = error


class _FakeTreeSitterParser:
    def __init__(self) -> None:
        self.detect_language = MagicMock(return_value=_FakeSupportedLanguage.PYTHON)
        self.parse_file = AsyncMock(
            return_value=_FakeParseResult(
                success=True,
                complexity={"foo": _FakeComplexityMetrics()},
            )
        )
        self.shutdown = MagicMock()


def _install_fake_tree_sitter(
    monkeypatch: pytest.MonkeyPatch,
    parser: _FakeTreeSitterParser | None = _FakeTreeSitterParser(),
    *,
    language_loadable: bool = True,
) -> None:
    """Inject a fake ``mcp_common.parsing.tree_sitter`` module."""

    fake_module = MagicMock()
    fake_module.TreeSitterParser = MagicMock(return_value=parser)
    fake_module.SupportedLanguage = _FakeSupportedLanguage
    fake_module.ensure_language_loaded = MagicMock(return_value=language_loadable)

    sys.modules["mcp_common.parsing.tree_sitter"] = fake_module
    monkeypatch.setitem(
        sys.modules, "mcp_common.parsing.tree_sitter", fake_module
    )


@pytest.fixture
def parser() -> _FakeTreeSitterParser:
    """A fresh fake parser; tests can customise ``parse_file``/``detect_language``."""
    return _FakeTreeSitterParser()


@pytest.fixture
async def adapter(
    monkeypatch: pytest.MonkeyPatch, parser: _FakeTreeSitterParser
) -> TreeSitterAdapter:
    """An initialized adapter wired up to the ``parser`` fixture."""
    _install_fake_tree_sitter(monkeypatch, parser=parser)
    a = TreeSitterAdapter()
    await a.init()
    # Ensure the adapter really is using the same parser instance.
    assert a._parser is parser
    return a


@pytest.fixture
async def adapter_no_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> TreeSitterAdapter:
    """An initialized adapter simulating a missing mcp_common tree_sitter."""
    fake_module = MagicMock()
    fake_module.TreeSitterParser = MagicMock(side_effect=ImportError("not installed"))

    sys.modules["mcp_common.parsing.tree_sitter"] = fake_module
    monkeypatch.setitem(
        sys.modules, "mcp_common.parsing.tree_sitter", fake_module
    )

    a = TreeSitterAdapter()
    await a.init()
    return a


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_module_id_is_uuid(self) -> None:
        assert str(MODULE_ID) == "12345678-1234-5678-1234-567812345679"

    def test_module_status_is_stable(self) -> None:
        assert AdapterStatus.STABLE.value == "stable"

    def test_alias_matches_main_class(self) -> None:
        assert TreeSitterQualityAdapter is TreeSitterAdapter


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestTreeSitterSettings:
    def test_default_settings(self) -> None:
        s = TreeSitterSettings()
        assert s.max_complexity == 15
        assert s.max_nesting_depth == 4
        assert s.max_parameters == 7
        assert s.max_returns == 5
        assert ".py" in s.supported_extensions
        assert ".go" in s.supported_extensions

    def test_supported_extensions_is_a_fresh_copy(self) -> None:
        """Each instance must have its own list (no mutable default sharing)."""
        a = TreeSitterSettings()
        b = TreeSitterSettings()
        a.supported_extensions.append(".swift")
        assert ".swift" not in b.supported_extensions

    def test_max_complexity_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_complexity=0)

    def test_max_complexity_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_complexity=101)

    def test_max_nesting_depth_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_nesting_depth=0)
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_nesting_depth=11)

    def test_max_parameters_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_parameters=0)
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_parameters=21)

    def test_max_returns_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_returns=0)
        with pytest.raises(ValidationError):
            TreeSitterSettings(max_returns=21)


# ---------------------------------------------------------------------------
# Adapter basics
# ---------------------------------------------------------------------------


class TestTreeSitterAdapterBasics:
    def test_default_init_state(self) -> None:
        a = TreeSitterAdapter()
        assert a.settings is None
        assert a._parser is None
        assert a._initialized is False

    def test_adapter_name(self) -> None:
        assert TreeSitterAdapter().adapter_name == "tree-sitter"

    def test_module_id(self) -> None:
        assert TreeSitterAdapter().module_id == MODULE_ID

    def test_get_check_type(self) -> None:
        a = TreeSitterAdapter()
        assert a._get_check_type() == QACheckType.COMPLEXITY


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------


class TestTreeSitterAdapterInit:
    async def test_init_creates_default_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_tree_sitter(monkeypatch)
        a = TreeSitterAdapter()
        assert a.settings is None
        await a.init()
        assert a.settings is not None
        assert a.settings.max_complexity == 15

    async def test_init_preserves_existing_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_tree_sitter(monkeypatch)
        a = TreeSitterAdapter()
        a.settings = TreeSitterSettings(max_complexity=42)
        await a.init()
        assert a.settings is not None
        assert a.settings.max_complexity == 42

    async def test_init_loads_parser(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_fake_tree_sitter(monkeypatch)
        a = TreeSitterAdapter()
        await a.init()
        assert a._parser is not None
        assert a._initialized is True

    async def test_init_handles_import_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate mcp-common[treesitter] not being installed.
        fake_module = MagicMock()
        fake_module.TreeSitterParser = MagicMock(
            side_effect=ImportError("treesitter not installed")
        )
        sys.modules["mcp_common.parsing.tree_sitter"] = fake_module
        monkeypatch.setitem(
            sys.modules, "mcp_common.parsing.tree_sitter", fake_module
        )

        a = TreeSitterAdapter()
        await a.init()
        # init() must not raise even when the optional parser is missing.
        assert a._parser is None
        assert a._initialized is True


# ---------------------------------------------------------------------------
# check() — top-level behavior
# ---------------------------------------------------------------------------


class TestCheckTopLevel:
    async def test_check_initializes_on_demand(self, adapter: TreeSitterAdapter) -> None:
        # Adapter fixture already ran init(); force a fresh, uninitialized instance
        # and ensure check() triggers init().
        fresh = TreeSitterAdapter()
        assert fresh._initialized is False
        with patch.object(fresh, "init", wraps=fresh.init) as spy:
            result = await fresh.check()
        spy.assert_awaited()
        assert isinstance(result, QAResult)

    async def test_check_returns_error_when_parser_unavailable(
        self, adapter_no_parser: TreeSitterAdapter
    ) -> None:
        result = await adapter_no_parser.check()
        assert result.status == QAResultStatus.ERROR
        assert "Tree-sitter parser not available" in result.message

    async def test_check_returns_skipped_when_no_files(
        self, adapter: TreeSitterAdapter
    ) -> None:
        result = await adapter.check(files=[])
        assert result.status == QAResultStatus.SKIPPED
        assert "No files to check" in result.message

    async def test_check_returns_skipped_when_all_files_filtered(
        self, adapter: TreeSitterAdapter
    ) -> None:
        # No supported extension -> filtered out in _prepare_files_to_check.
        result = await adapter.check(files=[Path("README.md")])
        assert result.status == QAResultStatus.SKIPPED
        assert "No files to check" in result.message

    async def test_check_with_supported_file_runs_parser(
        self, adapter: TreeSitterAdapter
    ) -> None:
        f = Path("hello.py")
        with patch.object(
            adapter, "_check_file", AsyncMock(return_value=[])
        ) as cf:
            result = await adapter.check(files=[f])
        cf.assert_awaited_once_with(f)
        assert result.status == QAResultStatus.SUCCESS
        assert result.issues_found == 0
        assert result.files_checked == [f]

    async def test_check_propagates_issues_to_result(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        # Provide an issue so _determine_status is exercised.
        issues = [
            {
                "file": Path("hello.py"),
                "line": 1,
                "column": 1,
                "code": "TS001",
                "severity": "warning",
                "message": "complex",
            }
        ]
        with patch.object(adapter, "_check_file", AsyncMock(return_value=issues)):
            result = await adapter.check(files=[Path("hello.py")])
        assert result.issues_found == 1
        assert result.parsed_issues == issues
        assert result.status == QAResultStatus.WARNING
        # Metadata reports the per-rule counts.
        assert result.metadata["complexity_issues"] == 1


# ---------------------------------------------------------------------------
# _check_file / rule emission
# ---------------------------------------------------------------------------


class TestCheckFileRuleEmission:
    async def test_check_file_skips_unknown_language(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.detect_language.return_value = (
            _FakeSupportedLanguage.UNKNOWN
        )
        result = await adapter._check_file(Path("hello.py"))
        assert result == []
        parser.parse_file.assert_not_awaited()

    async def test_check_file_skips_when_language_not_loaded(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        # ensure_language_loaded is patched to return False.
        with patch(
            "mcp_common.parsing.tree_sitter.ensure_language_loaded",
            return_value=False,
        ):
            result = await adapter._check_file(Path("hello.py"))
        assert result == []
        parser.parse_file.assert_not_awaited()

    async def test_check_file_skips_when_parse_fails(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(success=False)
        result = await adapter._check_file(Path("hello.py"))
        assert result == []

    async def test_check_file_emits_ts001_complexity(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(
            success=True,
            complexity={
                "fn": _FakeComplexityMetrics(cyclomatic=99),
            },
        )
        result = await adapter._check_file(Path("hello.py"))
        assert len(result) == 1
        issue = result[0]
        assert issue["code"] == "TS001"
        assert issue["severity"] == "warning"
        assert "Cyclomatic complexity 99" in issue["message"]
        assert "refactoring" in issue["suggestion"].lower()

    async def test_check_file_emits_ts002_nesting(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(
            success=True,
            complexity={
                "fn": _FakeComplexityMetrics(nesting_depth=8),
            },
        )
        result = await adapter._check_file(Path("hello.py"))
        assert len(result) == 1
        assert result[0]["code"] == "TS002"
        assert "Deep nesting (8 levels)" in result[0]["message"]

    async def test_check_file_emits_ts003_parameters(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(
            success=True,
            complexity={
                "fn": _FakeComplexityMetrics(num_parameters=20),
            },
        )
        result = await adapter._check_file(Path("hello.py"))
        assert len(result) == 1
        assert result[0]["code"] == "TS003"
        assert result[0]["severity"] == "info"
        assert "Too many parameters (20)" in result[0]["message"]

    async def test_check_file_emits_multiple_issues_for_same_symbol(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(
            success=True,
            complexity={
                "fn": _FakeComplexityMetrics(
                    cyclomatic=99, nesting_depth=8, num_parameters=20
                ),
            },
        )
        result = await adapter._check_file(Path("hello.py"))
        codes = sorted(issue["code"] for issue in result)
        assert codes == ["TS001", "TS002", "TS003"]

    async def test_check_file_emits_no_issues_when_within_thresholds(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        parser.parse_file.return_value = _FakeParseResult(
            success=True,
            complexity={
                "fn": _FakeComplexityMetrics(
                    cyclomatic=1, nesting_depth=0, num_parameters=0
                ),
            },
        )
        result = await adapter._check_file(Path("hello.py"))
        assert result == []

    async def test_check_file_with_error_handling_swallows_exceptions(
        self, adapter: TreeSitterAdapter
    ) -> None:
        with patch.object(
            adapter,
            "_check_file",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await adapter._check_file_with_error_handling(
                Path("hello.py")
            )
        assert result == []


# ---------------------------------------------------------------------------
# _determine_status
# ---------------------------------------------------------------------------


class TestDetermineStatus:
    def test_empty_issues_is_success(self) -> None:
        assert (
            TreeSitterAdapter._determine_status([]) == QAResultStatus.SUCCESS
        )

    def test_only_warnings_is_warning(self) -> None:
        issues = [{"severity": "warning"}, {"severity": "info"}]
        assert (
            TreeSitterAdapter._determine_status(issues) == QAResultStatus.WARNING
        )

    def test_any_error_is_failure(self) -> None:
        issues = [{"severity": "warning"}, {"severity": "error"}]
        assert (
            TreeSitterAdapter._determine_status(issues) == QAResultStatus.FAILURE
        )


# ---------------------------------------------------------------------------
# _update_metrics
# ---------------------------------------------------------------------------


class TestUpdateMetrics:
    def test_counts_files_and_rule_categories(self) -> None:
        metrics = {
            "files_checked": 0,
            "total_symbols": 0,
            "complexity_issues": 0,
            "nesting_issues": 0,
            "parameter_issues": 0,
        }
        issues = [
            {"code": "TS001"},
            {"code": "TS002"},
            {"code": "TS003"},
            {"code": "TS999"},  # Unknown rule should not affect any counter.
        ]
        TreeSitterAdapter._update_metrics(metrics, issues, Path("hello.py"))
        assert metrics["files_checked"] == 1
        assert metrics["complexity_issues"] == 1
        assert metrics["nesting_issues"] == 1
        assert metrics["parameter_issues"] == 1

    def test_empty_issues_still_counts_file(self) -> None:
        metrics = {
            "files_checked": 0,
            "total_symbols": 0,
            "complexity_issues": 0,
            "nesting_issues": 0,
            "parameter_issues": 0,
        }
        TreeSitterAdapter._update_metrics(metrics, [], Path("hello.py"))
        assert metrics["files_checked"] == 1
        assert metrics["complexity_issues"] == 0


# ---------------------------------------------------------------------------
# _prepare_files_to_check
# ---------------------------------------------------------------------------


class TestPrepareFilesToCheck:
    async def test_filters_by_supported_extension(
        self, adapter: TreeSitterAdapter
    ) -> None:
        adapter.settings = TreeSitterSettings(
            supported_extensions=[".py", ".go"]
        )
        files = [Path("a.py"), Path("b.go"), Path("c.txt"), Path("d.md")]
        result = adapter._prepare_files_to_check(files, config=None)
        assert result == [Path("a.py"), Path("b.go")]

    async def test_respects_config_include_and_exclude(
        self, adapter: TreeSitterAdapter
    ) -> None:
        adapter.settings = TreeSitterSettings(supported_extensions=[".py"])
        config = QACheckConfig(
            check_id=MODULE_ID,
            check_name="tree-sitter",
            check_type=QACheckType.COMPLEXITY,
            file_patterns=["*.py"],
            exclude_patterns=["*skip*.py"],
        )
        files = [Path("include.py"), Path("skip_this.py"), Path("also_skip.py")]
        result = adapter._prepare_files_to_check(files, config=config)
        assert result == [Path("include.py")]

    async def test_returns_empty_when_files_is_none(
        self, adapter: TreeSitterAdapter
    ) -> None:
        result = adapter._prepare_files_to_check(None, config=None)
        assert result == []


# ---------------------------------------------------------------------------
# _build_message
# ---------------------------------------------------------------------------


class TestBuildMessage:
    def test_no_issues(self) -> None:
        msg = TreeSitterAdapter._build_message(TreeSitterAdapter(), [], {})
        assert msg == "No issues found"

    def test_message_includes_per_rule_counts(self) -> None:
        metrics = {
            "complexity_issues": 2,
            "nesting_issues": 1,
            "parameter_issues": 3,
        }
        issues = [
            {"code": "TS001"},
            {"code": "TS001"},
            {"code": "TS002"},
        ]
        msg = TreeSitterAdapter._build_message(
            TreeSitterAdapter(), issues, metrics
        )
        assert "3 issues" in msg
        assert "2 complexity" in msg
        assert "1 nesting" in msg
        assert "3 parameter" in msg

    def test_message_omits_zero_count_categories(self) -> None:
        metrics = {
            "complexity_issues": 0,
            "nesting_issues": 1,
            "parameter_issues": 0,
        }
        msg = TreeSitterAdapter._build_message(
            TreeSitterAdapter(), [{"code": "TS002"}], metrics
        )
        assert "nesting" in msg
        assert "complexity" not in msg
        assert "parameter" not in msg


# ---------------------------------------------------------------------------
# _build_details
# ---------------------------------------------------------------------------


class TestBuildDetails:
    def test_includes_first_ten_issues(self) -> None:
        issues = [
            {
                "file": Path(f"f{i}.py"),
                "line": i,
                "code": "TS001",
                "message": f"msg-{i}",
            }
            for i in range(1, 6)
        ]
        details = TreeSitterAdapter._build_details(
            TreeSitterAdapter(), issues
        )
        for i in range(1, 6):
            assert f"f{i}.py:{i}: [TS001] msg-{i}" in details

    def test_truncates_with_summary_when_more_than_ten(self) -> None:
        issues = [
            {
                "file": Path(f"f{i}.py"),
                "line": i,
                "code": "TS001",
                "message": "x",
            }
            for i in range(15)
        ]
        details = TreeSitterAdapter._build_details(
            TreeSitterAdapter(), issues
        )
        # 10 detailed lines + 1 summary line.
        assert details.count("\n") == 10
        assert "and 5 more issues" in details

    def test_handles_missing_line(self) -> None:
        issues = [{"file": Path("f.py"), "code": "TS001", "message": "x"}]
        details = TreeSitterAdapter._build_details(
            TreeSitterAdapter(), issues
        )
        # No trailing colon for line when line is missing.
        assert "f.py: [TS001] x" in details


# ---------------------------------------------------------------------------
# get_default_config
# ---------------------------------------------------------------------------


class TestGetDefaultConfig:
    async def test_returns_sensible_config(
        self, adapter: TreeSitterAdapter
    ) -> None:
        config = adapter.get_default_config()
        assert isinstance(config, QACheckConfig)
        assert config.check_id == MODULE_ID
        assert config.check_name == "tree-sitter"
        assert config.check_type == QACheckType.COMPLEXITY
        assert config.enabled is True
        assert "*.py" in config.file_patterns
        assert "*.go" in config.file_patterns
        assert any("tests" in p for p in config.exclude_patterns)
        assert config.parallel_safe is True
        assert config.stage == "comprehensive"
        assert config.settings["max_complexity"] == 15
        assert config.settings["max_nesting_depth"] == 4
        assert config.settings["max_parameters"] == 7


# ---------------------------------------------------------------------------
# health_check / _cleanup
# ---------------------------------------------------------------------------


class TestHealthCheck:
    async def test_reports_parser_available_when_loaded(
        self, adapter: TreeSitterAdapter
    ) -> None:
        health = await adapter.health_check()
        assert health["parser_available"] is True
        assert health["status"] == "healthy"

    async def test_reports_parser_unavailable_when_missing(
        self, adapter_no_parser: TreeSitterAdapter
    ) -> None:
        health = await adapter_no_parser.health_check()
        assert health["parser_available"] is False


class TestCleanup:
    async def test_cleanup_shuts_down_parser(
        self, adapter: TreeSitterAdapter, parser: _FakeTreeSitterParser
    ) -> None:
        await adapter._cleanup()
        parser.shutdown.assert_called_once()
        assert adapter._parser is None

    async def test_cleanup_is_safe_when_parser_is_none(
        self, adapter_no_parser: TreeSitterAdapter
    ) -> None:
        # Must not raise even when the parser was never installed.
        await adapter_no_parser._cleanup()
        assert adapter_no_parser._parser is None

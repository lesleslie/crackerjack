"""Tests for SkylosAdapter dead code detection."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.adapters.lsp.skylos import (
    DeadCodeIssue,
    SkylosAdapter,
)


class TestDeadCodeIssue:
    """Test DeadCodeIssue dataclass."""

    def test_dead_code_issue_creation(self):
        """Test DeadCodeIssue creation."""
        issue = DeadCodeIssue(
            file_path=Path("test.py"),
            line_number=10,
            message="Dead function: foo",
        )
        assert issue.severity == "warning"
        assert issue.issue_type == "unknown"
        assert issue.name == "unknown"
        assert issue.confidence == 0.0

    def test_dead_code_issue_with_all_fields(self):
        """Test DeadCodeIssue with all fields."""
        issue = DeadCodeIssue(
            file_path=Path("main.py"),
            line_number=42,
            message="Dead import: os",
            severity="warning",
            issue_type="import",
            name="os",
            confidence=99.5,
        )
        assert issue.issue_type == "import"
        assert issue.name == "os"
        assert issue.confidence == 99.5

    def test_dead_code_issue_to_dict(self):
        """Test DeadCodeIssue.to_dict() method."""
        issue = DeadCodeIssue(
            file_path=Path("test.py"),
            line_number=10,
            message="Dead class: Foo",
            severity="warning",
            issue_type="class",
            name="Foo",
            confidence=98.0,
        )
        d = issue.to_dict()
        assert d["file_path"] == "test.py"
        assert d["issue_type"] == "class"
        assert d["name"] == "Foo"
        assert d["confidence"] == 98.0


class ConcreteSkylosAdapter(SkylosAdapter):
    """Concrete implementation for testing abstract methods."""

    def get_command_args(self, target_files):
        return ["skylos"]

    def parse_output(self, output):
        return super().parse_output(output)


class TestSkylosAdapter:
    """Test SkylosAdapter."""

    def test_initialization(self):
        """Test adapter initialization."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        assert adapter.get_tool_name() == "skylos"
        assert adapter.confidence_threshold == 99
        assert adapter.web_dashboard_port == 5090

    def test_initialization_custom(self):
        """Test adapter initialization with custom values."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(
            context=mock_context,
            confidence_threshold=95,
            web_dashboard_port=6000,
        )

        assert adapter.confidence_threshold == 95
        assert adapter.web_dashboard_port == 6000

    def test_supports_json_output(self):
        """Test supports_json_output returns True."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)
        assert adapter.supports_json_output() is True

    def test_get_command_args_basic(self):
        """Test get_command_args returns basic command."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        args = adapter.get_command_args([])
        assert args[0] == "uv"
        assert args[1] == "run"
        assert args[2] == "skylos"
        assert "--confidence" in args

    def test_get_command_args_with_json_mode(self):
        """Test get_command_args includes --json in AI mode."""
        mock_context = Mock()
        mock_context.ai_agent_mode = True
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        args = adapter.get_command_args([])
        assert "--json" in args

    def test_get_command_args_with_web_dashboard(self):
        """Test get_command_args includes web flags in interactive mode."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = True

        adapter = SkylosAdapter(mock_context)

        args = adapter.get_command_args([])
        assert "--web" in args
        assert "--port" in args
        assert str(adapter.web_dashboard_port) in args

    def test_determine_package_target(self):
        """Test _determine_package_target method."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        with patch.object(Path, "cwd", return_value=Path("/test")):
            with patch.object(adapter, "_get_package_name_from_pyproject", return_value=None):
                with patch.object(adapter, "_find_package_directory_with_init", return_value=None):
                    target = adapter._determine_package_target()
                    assert target == "./crackerjack"

    def test_get_package_name_from_pyproject_exists(self, tmp_path):
        """Test _get_package_name_from_pyproject with valid pyproject.toml."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-package"\n')

        with patch.object(Path, "cwd", return_value=tmp_path):
            name = adapter._get_package_name_from_pyproject(tmp_path)
            assert name == "my_package"

    def test_get_package_name_from_pyproject_missing(self, tmp_path):
        """Test _get_package_name_from_pyproject when no pyproject.toml."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        with patch.object(Path, "cwd", return_value=tmp_path):
            name = adapter._get_package_name_from_pyproject(tmp_path)
            assert name is None

    def test_find_package_directory_with_init(self, tmp_path):
        """Test _find_package_directory_with_init finds package."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").touch()

        with patch.object(Path, "cwd", return_value=tmp_path):
            name = adapter._find_package_directory_with_init(tmp_path)
            assert name == "mypackage"

    def test_find_package_directory_excludes_tests(self, tmp_path):
        """Test _find_package_directory_with_init excludes tests dir."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()

        with patch.object(Path, "cwd", return_value=tmp_path):
            name = adapter._find_package_directory_with_init(tmp_path)
            assert name is None

    def test_filter_package_files(self, tmp_path):
        """Test _filter_package_files filters correctly."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").touch()

        src_file = pkg_dir / "module.py"
        src_file.touch()

        test_file = tmp_path / "tests" / "test_module.py"
        test_file.touch()

        with patch.object(Path, "cwd", return_value=tmp_path):
            with patch.object(adapter, "_get_package_name_from_pyproject", return_value="mypackage"):
                filtered = adapter._filter_package_files([src_file, test_file])
                assert src_file in filtered
                assert test_file not in filtered

    def test_parse_json_output_success(self):
        """Test _parse_json_output with valid JSON."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        json_data = {
            "dead_code": [
                {"file": "src/main.py", "line": 10, "type": "function", "name": "unused_func"},
            ]
        }
        output = json.dumps(json_data)

        result = adapter._parse_json_output(output)

        assert result.success is False
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 10

    def test_parse_json_output_invalid(self):
        """Test _parse_json_output with invalid JSON."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        result = adapter._parse_json_output("not valid json")

        assert result.success is False
        assert result.error is not None

    def test_parse_text_output_empty(self):
        """Test _parse_text_output with empty output."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        result = adapter._parse_text_output("")

        assert result.success is True
        assert len(result.issues) == 0

    def test_parse_text_line_valid(self):
        """Test _parse_text_line with valid line."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        line = "src/main.py:10: Unused import 'os' (confidence: 95%)"
        issue = adapter._parse_text_line(line)

        assert issue is not None
        assert issue.file_path == Path("src/main.py")
        assert issue.line_number == 10

    def test_parse_text_line_invalid(self):
        """Test _parse_text_line with invalid line."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        line = "invalid line without proper format"
        issue = adapter._parse_text_line(line)

        assert issue is None

    def test_extract_basic_line_info_valid(self):
        """Test _extract_basic_line_info with valid line."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        line = "src/main.py:10: Some message"
        result = adapter._extract_basic_line_info(line)

        assert result is not None
        assert result[0] == Path("src/main.py")
        assert result[1] == 10
        assert result[2] == "Some message"

    def test_extract_basic_line_info_no_colon(self):
        """Test _extract_basic_line_info with no colon."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        result = adapter._extract_basic_line_info("invalid line")
        assert result is None

    def test_extract_issue_details_import(self):
        """Test _extract_issue_details with import message."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        details = adapter._extract_issue_details("Unused import 'os'")
        assert details["type"] == "import"
        assert details["name"] == "os"

    def test_extract_issue_details_function(self):
        """Test _extract_issue_details with function message."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        details = adapter._extract_issue_details("Unused function 'foo'")
        assert details["type"] == "function"
        assert details["name"] == "foo"

    def test_extract_issue_details_class(self):
        """Test _extract_issue_details with class message."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        details = adapter._extract_issue_details("Unused class 'Bar'")
        assert details["type"] == "class"
        assert details["name"] == "Bar"

    def test_extract_name_from_quotes(self):
        """Test _extract_name_from_quotes."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        name = adapter._extract_name_from_quotes("Unused import 'os' and more")
        assert name == "os"

    def test_extract_confidence_with_value(self):
        """Test _extract_confidence extracts value."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context, confidence_threshold=99)

        conf = adapter._extract_confidence("Some text (confidence: 95%)")
        assert conf == 95.0

    def test_extract_confidence_without_value(self):
        """Test _extract_confidence uses default."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context, confidence_threshold=99)

        conf = adapter._extract_confidence("Some text without confidence")
        assert conf == 99.0

    def test_cache_results(self, tmp_path):
        """Test _cache_results writes cache file."""
        mock_context = Mock()
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        adapter = SkylosAdapter(mock_context)

        data = {"dead_code": [], "target": "test"}

        with patch.object(Path, "cwd", return_value=tmp_path):
            adapter._cache_results(data)

            cache_dir = tmp_path / ".skylos_cache"
            assert cache_dir.exists()

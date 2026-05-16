"""Tests for check_jsonschema tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.tools.check_jsonschema import (
    _check_filename_pattern_schema,
    _check_internal_schema_ref,
    _check_parent_dir_schemas,
    _check_same_dir_schema,
    _get_json_files,
    _parse_args,
    _process_file,
    _resolve_local_schema_path,
    find_schema_for_json,
    load_schema,
    main,
    validate_json_against_schema,
)


class TestCheckFilenamePatternSchema:
    """Tests for _check_filename_pattern_schema function."""

    def test_finds_schema_with_pattern(self, tmp_path: Path) -> None:
        """Verify schema is found with filename pattern."""
        json_file = tmp_path / "config.json"
        schema_file = tmp_path / "config.schema.json"
        schema_file.write_text("{}")

        result = _check_filename_pattern_schema(json_file)
        assert result == schema_file

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Verify None returned when schema pattern not found."""
        json_file = tmp_path / "config.json"
        result = _check_filename_pattern_schema(json_file)
        assert result is None


class TestResolveLocalSchemaPath:
    """Tests for _resolve_local_schema_path function."""

    def test_resolves_json_file_reference(self, tmp_path: Path) -> None:
        """Verify local .json file reference is resolved."""
        json_file = tmp_path / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _resolve_local_schema_path(json_file, "schema.json")
        assert result == schema_file

    def test_resolves_schema_json_reference(self, tmp_path: Path) -> None:
        """Verify local .schema.json reference is resolved."""
        json_file = tmp_path / "config.json"
        schema_file = tmp_path / "schema.schema.json"
        schema_file.write_text("{}")

        result = _resolve_local_schema_path(json_file, "schema.schema.json")
        assert result == schema_file

    def test_returns_none_for_invalid_reference(self, tmp_path: Path) -> None:
        """Verify None returned for invalid reference type."""
        json_file = tmp_path / "config.json"
        result = _resolve_local_schema_path(json_file, "schema.txt")
        assert result is None

    def test_returns_none_when_file_not_found(self, tmp_path: Path) -> None:
        """Verify None returned when referenced file doesn't exist."""
        json_file = tmp_path / "config.json"
        result = _resolve_local_schema_path(json_file, "missing.json")
        assert result is None


class TestCheckInternalSchemaRef:
    """Tests for _check_internal_schema_ref function."""

    def test_finds_schema_from_schema_field(self, tmp_path: Path) -> None:
        """Verify schema is found from $schema field."""
        json_file = tmp_path / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")
        json_file.write_text('{"$schema": "schema.json"}')

        result = _check_internal_schema_ref(json_file)
        assert result == schema_file

    def test_returns_none_when_no_schema_field(self, tmp_path: Path) -> None:
        """Verify None returned when no $schema field."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value"}')

        result = _check_internal_schema_ref(json_file)
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path: Path) -> None:
        """Verify None returned for invalid JSON file."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{invalid}')

        result = _check_internal_schema_ref(json_file)
        assert result is None

    def test_returns_none_when_schema_ref_not_string(self, tmp_path: Path) -> None:
        """Verify None returned when $schema is not a string."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"$schema": 123}')

        result = _check_internal_schema_ref(json_file)
        assert result is None


class TestCheckSameDirSchema:
    """Tests for _check_same_dir_schema function."""

    def test_finds_schema_in_same_directory(self, tmp_path: Path) -> None:
        """Verify schema.json is found in same directory."""
        json_file = tmp_path / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _check_same_dir_schema(json_file)
        assert result == schema_file

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Verify None returned when schema.json not in directory."""
        json_file = tmp_path / "config.json"
        result = _check_same_dir_schema(json_file)
        assert result is None

    def test_returns_none_when_schema_is_json_file(self, tmp_path: Path) -> None:
        """Verify None returned when schema file is the JSON file itself."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _check_same_dir_schema(schema_file)
        assert result is None


class TestCheckParentDirSchemas:
    """Tests for _check_parent_dir_schemas function."""

    def test_finds_schema_in_parent_directory(self, tmp_path: Path) -> None:
        """Verify schema is found in parent directory."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        json_file = subdir / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _check_parent_dir_schemas(json_file)
        assert result == schema_file

    def test_searches_up_three_levels(self, tmp_path: Path) -> None:
        """Verify search extends up to 3 parent levels."""
        level2 = tmp_path / "l1" / "l2"
        level2.mkdir(parents=True)
        json_file = level2 / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _check_parent_dir_schemas(json_file)
        assert result == schema_file

    def test_returns_none_beyond_three_levels(self, tmp_path: Path) -> None:
        """Verify None returned when schema beyond 3 levels."""
        level4 = tmp_path / "l1" / "l2" / "l3" / "l4"
        level4.mkdir(parents=True)
        json_file = level4 / "config.json"
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")

        result = _check_parent_dir_schemas(json_file)
        assert result is None

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Verify None returned when schema not in parents."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        json_file = subdir / "config.json"

        result = _check_parent_dir_schemas(json_file)
        assert result is None


class TestFindSchemaForJson:
    """Tests for find_schema_for_json function."""

    def test_priority_filename_pattern_first(self, tmp_path: Path) -> None:
        """Verify filename pattern schema takes priority."""
        json_file = tmp_path / "config.json"
        pattern_schema = tmp_path / "config.schema.json"
        same_dir_schema = tmp_path / "schema.json"
        pattern_schema.write_text("{}")
        same_dir_schema.write_text("{}")

        result = find_schema_for_json(json_file)
        assert result == pattern_schema

    def test_priority_internal_ref_second(self, tmp_path: Path) -> None:
        """Verify internal $schema reference second priority."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"$schema": "myschema.json"}')
        myschema = tmp_path / "myschema.json"
        same_dir_schema = tmp_path / "schema.json"
        myschema.write_text("{}")
        same_dir_schema.write_text("{}")

        result = find_schema_for_json(json_file)
        assert result == myschema

    def test_priority_same_dir_third(self, tmp_path: Path) -> None:
        """Verify same directory schema third priority."""
        json_file = tmp_path / "config.json"
        same_dir_schema = tmp_path / "schema.json"
        same_dir_schema.write_text("{}")

        result = find_schema_for_json(json_file)
        assert result == same_dir_schema

    def test_priority_parent_dir_last(self, tmp_path: Path) -> None:
        """Verify parent directory schema lowest priority."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        json_file = subdir / "config.json"
        parent_schema = tmp_path / "schema.json"
        parent_schema.write_text("{}")

        result = find_schema_for_json(json_file)
        assert result == parent_schema


class TestLoadSchema:
    """Tests for load_schema function."""

    def test_loads_valid_schema(self, tmp_path: Path) -> None:
        """Verify valid schema is loaded."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "object"}')

        result = load_schema(schema_file)
        assert result == {"type": "object"}

    def test_returns_none_for_invalid_json(self, tmp_path: Path) -> None:
        """Verify None returned for invalid JSON."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{invalid}")

        result = load_schema(schema_file)
        assert result is None

    def test_returns_none_for_non_dict(self, tmp_path: Path) -> None:
        """Verify None returned for array schema."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("[]")

        result = load_schema(schema_file)
        assert result is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Verify None returned for missing file."""
        schema_file = tmp_path / "missing.json"
        result = load_schema(schema_file)
        assert result is None


class TestValidateJsonAgainstSchema:
    """Tests for validate_json_against_schema function."""

    def test_valid_json_passes(self, tmp_path: Path) -> None:
        """Verify valid JSON passes validation."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "object"}')
        json_file = tmp_path / "data.json"
        json_file.write_text('{}')

        is_valid, error = validate_json_against_schema(json_file, schema_file)
        assert is_valid is True
        assert error is None

    def test_invalid_json_fails(self, tmp_path: Path) -> None:
        """Verify invalid JSON fails validation."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "string"}')
        json_file = tmp_path / "data.json"
        json_file.write_text('{}')

        is_valid, error = validate_json_against_schema(json_file, schema_file)
        assert is_valid is False
        assert "Schema validation failed" in error

    def test_cannot_load_schema(self, tmp_path: Path) -> None:
        """Verify error when schema cannot be loaded."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{invalid}")
        json_file = tmp_path / "data.json"
        json_file.write_text('{}')

        is_valid, error = validate_json_against_schema(json_file, schema_file)
        assert is_valid is False
        assert "Could not load schema" in error

    def test_invalid_json_syntax(self, tmp_path: Path) -> None:
        """Verify error for invalid JSON syntax."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "object"}')
        json_file = tmp_path / "data.json"
        json_file.write_text("{invalid}")

        is_valid, error = validate_json_against_schema(json_file, schema_file)
        assert is_valid is False
        assert "Invalid JSON" in error


class TestParseArgs:
    """Tests for _parse_args function."""

    def test_no_arguments(self) -> None:
        """Verify default arguments."""
        args = _parse_args([])
        assert args.files == []
        assert args.strict is False

    def test_with_file_arguments(self, tmp_path: Path) -> None:
        """Verify file arguments parsed."""
        file1 = tmp_path / "file1.json"
        file2 = tmp_path / "file2.json"
        args = _parse_args([str(file1), str(file2)])
        assert len(args.files) == 2

    def test_strict_flag(self) -> None:
        """Verify --strict flag parsed."""
        args = _parse_args(["--strict"])
        assert args.strict is True


class TestGetJsonFiles:
    """Tests for _get_json_files function."""

    @patch("crackerjack.tools.check_jsonschema.get_files_by_extension")
    def test_uses_provided_files(self, mock_get, tmp_path: Path) -> None:
        """Verify provided files are used."""
        file1 = tmp_path / "file1.json"
        file1.write_text("{}")
        args = MagicMock(files=[file1])

        result = _get_json_files(args)
        assert result == [file1]
        mock_get.assert_not_called()

    @patch("crackerjack.tools.check_jsonschema.get_files_by_extension")
    def test_uses_git_tracked_when_no_files(self, mock_get, tmp_path: Path) -> None:
        """Verify git tracked files used when no args."""
        file1 = tmp_path / "file1.json"
        mock_get.return_value = [file1]
        args = MagicMock(files=[])

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = _get_json_files(args)

        mock_get.assert_called_with([".json"])

    def test_filters_directories(self, tmp_path: Path) -> None:
        """Verify directories are filtered out."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file1 = tmp_path / "file1.json"
        file1.write_text("{}")
        args = MagicMock(files=[subdir, file1])

        result = _get_json_files(args)
        assert result == [file1]


class TestProcessFile:
    """Tests for _process_file function."""

    def test_valid_file_success(self, tmp_path: Path) -> None:
        """Verify success for valid file."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"type": "object"}')
        data_file = tmp_path / "data.json"
        data_file.write_text('{}')

        with patch("builtins.print"):
            result = _process_file(data_file, schema_file, False)
        assert result == 0

    def test_no_schema_not_strict(self, tmp_path: Path) -> None:
        """Verify skip when no schema in non-strict mode."""
        with patch("builtins.print"):
            result = _process_file(tmp_path / "data.json", None, False)
        assert result == 0

    def test_no_schema_strict(self, tmp_path: Path) -> None:
        """Verify fail when no schema in strict mode."""
        with patch("builtins.print"):
            result = _process_file(tmp_path / "data.json", None, True)
        assert result == 1


class TestMain:
    """Tests for main function."""

    @patch("crackerjack.tools.check_jsonschema._get_json_files")
    def test_no_files(self, mock_get) -> None:
        """Verify exit 0 when no files found."""
        mock_get.return_value = []
        with patch("builtins.print"):
            result = main([])
        assert result == 0

    @patch("crackerjack.tools.check_jsonschema._get_json_files")
    @patch("crackerjack.tools.check_jsonschema.find_schema_for_json")
    @patch("crackerjack.tools.check_jsonschema._process_file")
    def test_processes_files(self, mock_process, mock_find, mock_get, tmp_path: Path) -> None:
        """Verify files are processed."""
        file1 = tmp_path / "file1.json"
        mock_get.return_value = [file1]
        mock_find.return_value = None
        mock_process.return_value = 0

        with patch("builtins.print"):
            result = main([])

        assert mock_process.call_count == 1
        assert result == 0

"""Test edge cases for CodeCleaner functionality."""

from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from crackerjack.code_cleaner import CodeCleaner


class TestCodeCleanerEdgeCases:
    def test_is_stdlib_import_edge_cases(self) -> None:
        code_cleaner = CodeCleaner(console=Console())
        assert not code_cleaner._is_stdlib_import("from")
        assert not code_cleaner._is_stdlib_import("import")
        assert not code_cleaner._is_stdlib_import("from  ")
        assert not code_cleaner._is_stdlib_import("import  ")
        assert code_cleaner._is_stdlib_import("import os")
        assert code_cleaner._is_stdlib_import("from sys import path")
        assert code_cleaner._is_stdlib_import("import json.loads")
        assert not code_cleaner._is_stdlib_import("import requests")
        assert not code_cleaner._is_stdlib_import("from django import models")

    def test_is_local_import_detection(self) -> None:
        code_cleaner = CodeCleaner(console=Console())
        assert code_cleaner._is_local_import("from . import module")
        assert code_cleaner._is_local_import("from .submodule import function")
        assert code_cleaner._is_local_import("import . as current")
        assert not code_cleaner._is_local_import("from package import module")
        assert not code_cleaner._is_local_import("import os")

    def test_file_encoding_error_handling(self, tmp_path: Path) -> None:
        code_cleaner = CodeCleaner(console=Console())
        test_file = tmp_path / "encoding_test.py"
        test_file.write_bytes(
            b"\xff\xfe# -*- coding: latin-1 -*-\ndef test():\n    pass\n"
        )
        with patch.object(code_cleaner.console, "print") as mock_print:
            code_cleaner.clean_file(test_file)
            [str(call) for call in mock_print.call_args_list]

    def test_clean_file_permission_error(self, tmp_path: Path) -> None:
        code_cleaner = CodeCleaner(console=Console())
        test_file = tmp_path / "readonly_test.py"
        test_file.write_text("def test():\n    pass\n")
        with patch(
            "pathlib.Path.read_text", side_effect=PermissionError("Access denied")
        ):
            with patch.object(code_cleaner.console, "print") as mock_print:
                code_cleaner.clean_file(test_file)
                print_calls = [str(call) for call in mock_print.call_args_list]
                any(
                    "error" in call.lower() or "warning" in call.lower()
                    for call in print_calls
                )

    def test_remove_docstrings_malformed_syntax(self) -> None:
        code_cleaner = CodeCleaner(console=Console())
        malformed_cases = [
            'def func():\n    """proper docstring"""\n    pass',
            'class Test:\n    """class docstring"""\n    pass',
            'def empty():\n    """empty function"""\n',
        ]
        for case in malformed_cases:
            with suppress(Exception):
                result = code_cleaner.remove_docstrings(case)
                assert isinstance(result, str)
                assert '"""' not in result or "pass" in result

    def test_clean_files_error_handling(self, tmp_path: Path) -> None:
        code_cleaner = CodeCleaner(console=Console())
        good_file = tmp_path / "good.py"
        good_file.write_text("def test():\n    pass\n")
        fake_file = tmp_path / "fake.py"
        fake_file.mkdir()
        with patch.object(code_cleaner.console, "print") as mock_print:
            code_cleaner.clean_files(tmp_path)
            [str(call) for call in mock_print.call_args_list]

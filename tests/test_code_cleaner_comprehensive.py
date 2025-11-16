import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.code_cleaner import (
    CodeCleaner,
    CleaningResult,
    PackageCleaningResult,
    SafePatternApplicator,
)


class TestSafePatternApplicator:
    def test_apply_docstring_patterns(self):
        """Test applying docstring patterns"""
        applicator = SafePatternApplicator()

        # Test with docstring patterns
        code_with_docstrings = '''def func():
    """This is a docstring."""
    pass'''

        result = applicator.apply_docstring_patterns(code_with_docstrings)
        # The result should be the same since we're not changing docstrings
        assert result == code_with_docstrings

    def test_apply_formatting_patterns(self):
        """Test applying formatting patterns"""
        applicator = SafePatternApplicator()

        # Test spacing after comma
        code_with_comma_spaces = "func(a,b,c)"
        expected = "func(a, b, c)"
        result = applicator.apply_formatting_patterns(code_with_comma_spaces)
        assert result == expected

        # Test spacing after colon
        code_with_colon_spaces = "dict = {key:value}"
        expected = "dict = {key: value}"
        result = applicator.apply_formatting_patterns(code_with_colon_spaces)
        assert result == expected

        # Test multiple spaces
        code_with_multiple_spaces = "x   =   5"
        expected = "x = 5"
        result = applicator.apply_formatting_patterns(code_with_multiple_spaces)
        assert result == expected

    def test_has_preserved_comment(self):
        """Test has_preserved_comment method"""
        applicator = SafePatternApplicator()

        # Test shebang comments (still useful for executable scripts)
        assert applicator.has_preserved_comment("#!/usr/bin/env python3") is True
        assert applicator.has_preserved_comment("#! /usr/bin/env python") is True

        # Test nosec comments (Bandit security suppression - critical)
        assert applicator.has_preserved_comment("# nosec B311") is True
        assert applicator.has_preserved_comment("    # nosec B608") is True
        assert applicator.has_preserved_comment("# nosec") is True

        # Test other critical preserved patterns
        assert applicator.has_preserved_comment("# type: ignore") is True
        assert applicator.has_preserved_comment("# noqa") is True
        assert applicator.has_preserved_comment("# pragma: no cover") is True
        assert applicator.has_preserved_comment("# TODO: fix this") is True

        # Test obsolete encoding declarations (should NOT be preserved - Python 3.0+)
        assert applicator.has_preserved_comment("# coding: utf-8") is False
        assert applicator.has_preserved_comment("# -*- coding: utf-8 -*-") is False

        # Test regular comment
        assert applicator.has_preserved_comment("# This is a regular comment") is False

    def test_inline_nosec_preservation(self):
        """Test that inline nosec comments are preserved"""
        from crackerjack.code_cleaner import CodeCleaner
        from pathlib import Path
        import tempfile

        cleaner = CodeCleaner(console=Console(), base_directory=Path(tempfile.gettempdir()))

        # Test code with inline nosec comments
        test_code = '''import random
value = random.random()  # nosec B311
other = 123  # regular comment
result = value * 2  # type: ignore
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_path = Path(f.name)

        try:
            result = cleaner.clean_file(temp_path)
            cleaned = temp_path.read_text()

            # Verify nosec and type: ignore are preserved
            assert '# nosec B311' in cleaned
            assert '# type: ignore' in cleaned
            # Verify regular comment is removed
            assert '# regular comment' not in cleaned

        finally:
            temp_path.unlink()


class TestCodeCleaner:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def cleaner(self, console):
        return CodeCleaner(console=console, base_directory=Path(tempfile.gettempdir()))

    def test_init(self, cleaner, console):
        """Test CodeCleaner initialization"""
        assert cleaner.console == console
        assert cleaner.base_directory == Path(tempfile.gettempdir())
        assert cleaner.logger is not None

    def test_prepare_package_directory_with_valid_path(self, cleaner):
        """Test _prepare_package_directory with valid path"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result = cleaner._prepare_package_directory(tmp_path)
            assert result == tmp_path

    def test_prepare_package_directory_with_none(self, cleaner):
        """Test _prepare_package_directory with None (should use base_directory)"""
        result = cleaner._prepare_package_directory(None)
        assert result == cleaner.base_directory

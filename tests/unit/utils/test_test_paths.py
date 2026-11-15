"""Tests for the test-path classifier used by the refurb hook."""

from __future__ import annotations

import pytest

from crackerjack.utils.test_paths import is_test_path


class TestIsTestPath:
    """The classifier decides what the refurb hook reports."""

    @pytest.mark.parametrize(
        "path",
        [
            "tests/unit/test_thing.py",
            "session_buddy/tests/test_thing.py",
            "session_buddy/tests/integration/test_thing.py",
            "test/unit/test_thing.py",
            "session_buddy/test/test_thing.py",
            "tests\\unit\\test_thing.py",
            "./session_buddy/tests/test_thing.py",
        ],
    )
    def test_directories_named_tests_or_test(self, path: str) -> None:
        """A tests/ or test/ directory component marks a test path."""
        assert is_test_path(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "session_buddy/utils/quality_scoring.py",
            "crackerjack/parsers/regex_parsers.py",
            "src/main.py",
            "session_buddy/testing/helper.py",
            "src/contest.py",
            "src/latest/module.py",
        ],
    )
    def test_production_paths_are_kept(self, path: str) -> None:
        """Production code is never classified as a test path."""
        assert is_test_path(path) is False

    @pytest.mark.parametrize(
        "path",
        [
            # Shipped modules whose names look like tests. Excluding these
            # would take real code out of the gate.
            "crackerjack/managers/test_progress.py",
            "crackerjack/managers/test_executor.py",
            "crackerjack/managers/test_command_builder.py",
            "mahavishnu/prototypes/opensearch_test.py",
            "mahavishnu/testing/load_test.py",
        ],
    )
    def test_test_looking_production_files_are_kept(self, path: str) -> None:
        """A test-shaped file name outside a test directory is production."""
        assert is_test_path(path) is False

    def test_empty_path(self) -> None:
        """An empty path is not a test path."""
        assert is_test_path("") is False

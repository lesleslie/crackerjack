from __future__ import annotations

import io
from unittest.mock import patch

from crackerjack.cli.version import get_package_version


class TestGetPackageVersion:
    def test_returns_package_metadata_version(self) -> None:
        with patch("importlib.metadata.version", return_value="9.8.7"):
            assert get_package_version() == "9.8.7"

    def test_falls_back_to_pyproject_version(self) -> None:
        pyproject = b"""
[project]
version = "1.2.3"
"""

        with (
            patch(
                "importlib.metadata.version",
                side_effect=ModuleNotFoundError,
            ),
            patch("crackerjack.cli.version.Path.open", return_value=io.BytesIO(pyproject)),
        ):
            assert get_package_version() == "1.2.3"

    def test_returns_unknown_when_all_fallbacks_fail(self) -> None:
        with (
            patch(
                "importlib.metadata.version",
                side_effect=ModuleNotFoundError,
            ),
            patch(
                "crackerjack.cli.version.Path.open",
                side_effect=FileNotFoundError,
            ),
        ):
            assert get_package_version() == "unknown"

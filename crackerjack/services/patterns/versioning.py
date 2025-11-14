"""Version number extraction and update patterns."""

import re

from .core import ValidatedPattern

PATTERNS: dict[str, ValidatedPattern] = {
    "extract_version_numbers": ValidatedPattern(
        name="extract_version_numbers",
        pattern=r"version\s+(\d+\.\d+\.\d+)",
        replacement=r"\1",
        description="Extract semantic version numbers from 'version X.Y.Z' patterns",
        flags=re.IGNORECASE,
        test_cases=[
            ("version 1.2.3", "1.2.3"),
            ("Version 10.0.1", "10.0.1"),
            ("current version 0.5.0", "current 0.5.0"),
            ("VERSION 2.11.4", "2.11.4"),
        ],
    ),
    "update_pyproject_version": ValidatedPattern(
        name="update_pyproject_version",
        pattern=r'^(version\s*=\s*["\'])([^"\']+)(["\'])$',
        replacement=r"\g<1>NEW_VERSION\g<3>",
        description="Update version in pyproject.toml files (NEW_VERSION placeholder"
        " replaced dynamically)",
        test_cases=[
            ('version = "1.2.3"', 'version = "NEW_VERSION"'),
            ("version='0.1.0'", "version='NEW_VERSION'"),
            ('version="1.0.0-beta"', 'version="NEW_VERSION"'),
            ("version = '2.1.0'", "version = 'NEW_VERSION'"),
            ("version='10.20.30'", "version='NEW_VERSION'"),
            ('name = "my-package"', 'name = "my-package"'),
        ],
    ),
    "update_repo_revision": ValidatedPattern(
        name="update_repo_revision",
        pattern=r'("repo": "[^"]+?".*?"rev": )"([^"]+)"',
        replacement=r'\1"NEW_REVISION"',
        description="Update repository revision in config files (NEW_REVISION"
        " placeholder replaced dynamically)",
        flags=re.DOTALL,
        test_cases=[
            (
                '"repo": "https: //github.com/user/repo".*"rev": "old_rev"',
                '"repo": "https: //github.com/user/repo".*"rev": "NEW_REVISION"',
            ),
            (
                '"repo": "git@github.com: user/repo.git", "branch": "main", "rev": '
                '"abc123"',
                '"repo": "git@github.com: user/repo.git", "branch": "main", "rev": '
                '"NEW_REVISION"',
            ),
            (
                '{"repo": "https: //example.com/repo", "description": "test", "rev": '
                '"456def"}',
                '{"repo": "https: //example.com/repo", "description": "test", "rev": '
                '"NEW_REVISION"}',
            ),
        ],
    ),
}

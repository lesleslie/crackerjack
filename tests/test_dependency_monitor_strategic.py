"""Strategic tests for dependency_monitor.py module.

Tests dependency parsing, vulnerability detection, update monitoring, and security features.
Focuses on real logic to maximize coverage toward 42% requirement.
"""

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.models.protocols import FileSystemInterface
from crackerjack.services.dependency_monitor import (
    DependencyMonitorService,
    DependencyVulnerability,
    MajorUpdate,
)


@pytest.fixture
def mock_filesystem():
    """Mock FilesystemInterface for dependency monitor testing."""
    fs = AsyncMock(spec=FileSystemInterface)
    return fs


@pytest.fixture
def mock_console():
    """Mock Rich Console for output testing."""
    console = Mock()
    console.print = Mock()
    return console


@pytest.fixture
def dependency_monitor(mock_filesystem, mock_console):
    """DependencyMonitorService instance with mocked dependencies."""
    service = DependencyMonitorService(
        filesystem=mock_filesystem,
        console=mock_console,
    )
    return service


@pytest.fixture
def sample_pyproject_content():
    """Sample pyproject.toml content for testing."""
    return b"""
[project]
name = "test-project"
dependencies = [
    "requests>=2.25.0",
    "click~=8.0.0",
    "pydantic==1.10.0",
    "fastapi>=0.68.0,<0.100.0",
    "uvicorn",
]

[project.optional-dependencies]
dev = [
    "pytest>=6.0.0",
    "black==22.3.0",
]
test = [
    "coverage>=5.0.0",
]
"""


@pytest.fixture
def mock_pyproject_path(dependency_monitor, sample_pyproject_content, tmp_path):
    """Create real pyproject.toml file for testing."""
    # Create a temporary directory with real pyproject.toml
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    pyproject_path = test_dir / "pyproject.toml"
    pyproject_path.write_bytes(sample_pyproject_content)

    # Set the dependency monitor to use the test directory
    dependency_monitor.project_root = test_dir
    dependency_monitor.pyproject_path = pyproject_path

    yield pyproject_path


class TestDependencyDataClasses:
    """Test dataclass models for dependency information."""

    def test_dependency_vulnerability_creation(self):
        """Test DependencyVulnerability dataclass initialization."""
        vuln = DependencyVulnerability(
            package="requests",
            installed_version="2.24.0",
            vulnerability_id="CVE-2023-1234",
            severity="HIGH",
            advisory_url="https://security.example.com/CVE-2023-1234",
            vulnerable_versions="<2.25.0",
            patched_version="2.25.0",
        )

        assert vuln.package == "requests"
        assert vuln.installed_version == "2.24.0"
        assert vuln.vulnerability_id == "CVE-2023-1234"
        assert vuln.severity == "HIGH"
        assert vuln.advisory_url == "https://security.example.com/CVE-2023-1234"
        assert vuln.vulnerable_versions == "<2.25.0"
        assert vuln.patched_version == "2.25.0"

    def test_major_update_creation(self):
        """Test MajorUpdate dataclass initialization."""
        update = MajorUpdate(
            package="fastapi",
            current_version="0.68.0",
            latest_version="1.0.0",
            release_date="2023-06-15T10:30:00",
            breaking_changes=True,
        )

        assert update.package == "fastapi"
        assert update.current_version == "0.68.0"
        assert update.latest_version == "1.0.0"
        assert update.release_date == "2023-06-15T10:30:00"
        assert update.breaking_changes is True


class TestDependencyMonitorInitialization:
    """Test DependencyMonitorService initialization and setup."""

    def test_initialization_with_console(self, mock_filesystem):
        """Test service initialization with custom console."""
        mock_console = Mock()
        service = DependencyMonitorService(
            filesystem=mock_filesystem,
            console=mock_console,
        )

        assert service.filesystem == mock_filesystem
        assert service.console == mock_console
        assert service.project_root == Path.cwd()
        assert service.pyproject_path == Path.cwd() / "pyproject.toml"
        assert (
            service.cache_file == Path.cwd() / ".crackerjack" / "dependency_cache.json"
        )

    def test_initialization_without_console(self, mock_filesystem):
        """Test service initialization with default console."""
        service = DependencyMonitorService(filesystem=mock_filesystem)

        assert service.filesystem == mock_filesystem
        assert service.console is not None  # Default Rich Console created
        assert service.project_root == Path.cwd()


class TestDependencyParsing:
    """Test dependency parsing from pyproject.toml."""

    def test_parse_dependencies_success(self, dependency_monitor, mock_pyproject_path):
        """Test successful dependency parsing from pyproject.toml."""
        dependencies = dependency_monitor._parse_dependencies()

        # Check main dependencies (parser extracts version part after first operator)
        assert dependencies["requests"] == "2.25.0"
        assert dependencies["click"] == "8.0.0"
        assert dependencies["pydantic"] == "1.10.0"
        assert (
            dependencies["fastapi"] == "0.68.0,<0.100.0"
        )  # Splits on ">=" and keeps rest
        assert dependencies["uvicorn"] == "latest"  # No version specified

        # Check optional dependencies
        assert dependencies["pytest"] == "6.0.0"
        assert dependencies["black"] == "22.3.0"
        assert dependencies["coverage"] == "5.0.0"

    def test_parse_dependencies_file_not_found(self, dependency_monitor, tmp_path):
        """Test dependency parsing when pyproject.toml doesn't exist."""
        # Create a temporary directory without pyproject.toml
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()

        # Set the dependency monitor to use the test directory
        dependency_monitor.project_root = test_dir
        dependency_monitor.pyproject_path = test_dir / "pyproject.toml"

        dependencies = dependency_monitor._parse_dependencies()
        assert dependencies == {}

    def test_parse_dependencies_invalid_toml(
        self, dependency_monitor, mock_console, tmp_path
    ):
        """Test dependency parsing with invalid TOML content."""
        # Create a temporary directory with invalid pyproject.toml
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()
        pyproject_path = test_dir / "pyproject.toml"
        pyproject_path.write_text("invalid toml content [[[")

        # Set the dependency monitor to use the test directory
        dependency_monitor.project_root = test_dir
        dependency_monitor.pyproject_path = pyproject_path

        dependencies = dependency_monitor._parse_dependencies()
        assert dependencies == {}

        # Check warning was printed
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0]
        assert "Failed to parse pyproject.toml" in args[0]

    def test_parse_dependency_spec_various_operators(self, dependency_monitor):
        """Test parsing dependency specifications with various operators."""
        test_cases = [
            ("requests>=2.25.0", ("requests", "2.25.0")),
            ("click~=8.0.0", ("click", "8.0.0")),
            ("pydantic==1.10.0", ("pydantic", "1.10.0")),
            ("fastapi!=0.60.0", ("fastapi", "0.60.0")),
            ("uvicorn>0.15.0", ("uvicorn", "0.15.0")),
            ("pytest<7.0.0", ("pytest", "7.0.0")),
            ("coverage<=6.0.0", ("coverage", "6.0.0")),
            ("simple-package", ("simple-package", "latest")),
            ("", (None, None)),
            ("-e git+https://github.com/user/repo.git", (None, None)),
        ]

        for spec, expected in test_cases:
            result = dependency_monitor._parse_dependency_spec(spec)
            assert result == expected

    def test_extract_main_dependencies_no_project_section(self, dependency_monitor):
        """Test extracting main dependencies when no project section exists."""
        dependencies = {}
        project_data = {}  # No dependencies key

        dependency_monitor._extract_main_dependencies(project_data, dependencies)
        assert dependencies == {}

    def test_extract_optional_dependencies_no_optional_section(
        self, dependency_monitor
    ):
        """Test extracting optional dependencies when no optional section exists."""
        dependencies = {}
        project_data = {}  # No optional-dependencies key

        dependency_monitor._extract_optional_dependencies(project_data, dependencies)
        assert dependencies == {}


class TestVulnerabilityChecking:
    """Test security vulnerability detection functionality."""

    def test_check_dependency_updates_no_pyproject(self, dependency_monitor, tmp_path):
        """Test update check when pyproject.toml doesn't exist."""
        # Create a temporary directory without pyproject.toml
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()

        # Set the dependency monitor to use the test directory
        dependency_monitor.project_root = test_dir
        dependency_monitor.pyproject_path = test_dir / "pyproject.toml"

        result = dependency_monitor.check_dependency_updates()
        assert result is False

    def test_check_dependency_updates_no_dependencies(self, dependency_monitor):
        """Test update check when no dependencies are found."""
        with patch.object(dependency_monitor, "_parse_dependencies", return_value={}):
            result = dependency_monitor.check_dependency_updates()
            assert result is False

    def test_check_dependency_updates_with_vulnerabilities(
        self, dependency_monitor, mock_console
    ):
        """Test update check when vulnerabilities are found."""
        mock_dependencies = {"requests": "2.24.0"}
        mock_vulnerabilities = [
            DependencyVulnerability(
                package="requests",
                installed_version="2.24.0",
                vulnerability_id="CVE-2023-1234",
                severity="HIGH",
                advisory_url="https://security.example.com",
                vulnerable_versions="<2.25.0",
                patched_version="2.25.0",
            )
        ]

        with patch.object(
            dependency_monitor, "_parse_dependencies", return_value=mock_dependencies
        ):
            with patch.object(
                dependency_monitor,
                "_check_security_vulnerabilities",
                return_value=mock_vulnerabilities,
            ):
                with patch.object(
                    dependency_monitor, "_report_vulnerabilities"
                ) as mock_report:
                    result = dependency_monitor.check_dependency_updates()

                    assert result is True
                    mock_report.assert_called_once_with(mock_vulnerabilities)

    def test_check_dependency_updates_with_major_updates(
        self, dependency_monitor, mock_console
    ):
        """Test update check when major updates are available."""
        mock_dependencies = {"fastapi": "0.68.0"}
        mock_major_updates = [
            MajorUpdate(
                package="fastapi",
                current_version="0.68.0",
                latest_version="1.0.0",
                release_date="2023-06-15",
                breaking_changes=True,
            )
        ]

        with patch.object(
            dependency_monitor, "_parse_dependencies", return_value=mock_dependencies
        ):
            with patch.object(
                dependency_monitor, "_check_security_vulnerabilities", return_value=[]
            ):
                with patch.object(
                    dependency_monitor,
                    "_check_major_updates",
                    return_value=mock_major_updates,
                ):
                    with patch.object(
                        dependency_monitor,
                        "_should_notify_major_updates",
                        return_value=True,
                    ):
                        with patch.object(
                            dependency_monitor, "_report_major_updates"
                        ) as mock_report:
                            result = dependency_monitor.check_dependency_updates()

                            assert result is True
                            mock_report.assert_called_once_with(mock_major_updates)

    def test_create_requirements_file(self, dependency_monitor):
        """Test creation of temporary requirements file."""
        dependencies = {
            "requests": "2.25.0",
            "click": "latest",
            "pydantic": "1.10.0",
        }

        temp_file = dependency_monitor._create_requirements_file(dependencies)

        try:
            with open(temp_file) as f:
                content = f.read()

            expected_lines = [
                "requests==2.25.0\n",
                "click\n",  # No version for "latest"
                "pydantic==1.10.0\n",
            ]

            for line in expected_lines:
                assert line in content
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_execute_vulnerability_command(self, dependency_monitor):
        """Test execution of vulnerability scanning command."""
        command_template = ["uv", "run", "safety", "--file", "__TEMP_FILE__"]
        temp_file = "/tmp/requirements.txt"

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = dependency_monitor._execute_vulnerability_command(
                command_template, temp_file
            )

            expected_cmd = ["uv", "run", "safety", "--file", temp_file]
            mock_run.assert_called_once_with(
                expected_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result == mock_result

    def test_process_vulnerability_result_no_vulnerabilities(self, dependency_monitor):
        """Test processing vulnerability scan result with no vulnerabilities."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        parser_func = Mock(return_value=[])
        result = dependency_monitor._process_vulnerability_result(
            mock_result, parser_func
        )

        assert result == []
        parser_func.assert_not_called()

    def test_process_vulnerability_result_with_vulnerabilities(
        self, dependency_monitor
    ):
        """Test processing vulnerability scan result with vulnerabilities found."""
        mock_result = Mock()
        mock_result.returncode = 1  # Non-zero indicates vulnerabilities found
        mock_result.stdout = '{"vulnerabilities": []}'

        expected_vulnerabilities = [
            DependencyVulnerability(
                package="test",
                installed_version="1.0.0",
                vulnerability_id="TEST-1",
                severity="HIGH",
                advisory_url="",
                vulnerable_versions="",
                patched_version="",
            )
        ]

        parser_func = Mock(return_value=expected_vulnerabilities)
        result = dependency_monitor._process_vulnerability_result(
            mock_result, parser_func
        )

        assert result == expected_vulnerabilities
        parser_func.assert_called_once_with({"vulnerabilities": []})

    def test_parse_safety_output(self, dependency_monitor):
        """Test parsing Safety tool output."""
        safety_data = [
            {
                "package": "requests",
                "installed_version": "2.24.0",
                "vulnerability_id": "CVE-2023-1234",
                "severity": "HIGH",
                "more_info_url": "https://security.example.com",
                "vulnerable_spec": "<2.25.0",
                "analyzed_version": "2.25.0",
            }
        ]

        vulnerabilities = dependency_monitor._parse_safety_output(safety_data)

        assert len(vulnerabilities) == 1
        vuln = vulnerabilities[0]
        assert vuln.package == "requests"
        assert vuln.installed_version == "2.24.0"
        assert vuln.vulnerability_id == "CVE-2023-1234"
        assert vuln.severity == "HIGH"
        assert vuln.advisory_url == "https://security.example.com"

    def test_parse_pip_audit_output(self, dependency_monitor):
        """Test parsing pip-audit tool output."""
        audit_data = {
            "vulnerabilities": [
                {
                    "package": {"name": "flask", "version": "1.0.0"},
                    "id": "PYSEC-2023-1234",
                    "severity": "CRITICAL",
                    "link": "https://osv.dev/PYSEC-2023-1234",
                    "vulnerable_ranges": "<2.0.0",
                    "fix_versions": ["2.0.0"],
                }
            ]
        }

        vulnerabilities = dependency_monitor._parse_pip_audit_output(audit_data)

        assert len(vulnerabilities) == 1
        vuln = vulnerabilities[0]
        assert vuln.package == "flask"
        assert vuln.installed_version == "1.0.0"
        assert vuln.vulnerability_id == "PYSEC-2023-1234"
        assert vuln.severity == "CRITICAL"
        assert vuln.patched_version == "2.0.0"


class TestMajorUpdateChecking:
    """Test major version update detection functionality."""

    def test_is_major_version_update_true(self, dependency_monitor):
        """Test major version update detection for valid cases."""
        test_cases = [
            ("1.0.0", "2.0.0"),  # 1 -> 2
            ("0.68.0", "1.0.0"),  # 0 -> 1
            ("2.1.5", "3.0.0"),  # 2 -> 3
        ]

        for current, latest in test_cases:
            result = dependency_monitor._is_major_version_update(current, latest)
            assert result is True, f"Expected {current} -> {latest} to be major update"

    def test_is_major_version_update_false(self, dependency_monitor):
        """Test major version update detection for non-major cases."""
        test_cases = [
            ("2.0.0", "2.1.0"),  # Minor update
            ("1.5.0", "1.5.1"),  # Patch update
            ("3.0.0", "2.9.0"),  # Downgrade
            ("1.0.0", "1.0.0"),  # Same version
        ]

        for current, latest in test_cases:
            result = dependency_monitor._is_major_version_update(current, latest)
            assert result is False, (
                f"Expected {current} -> {latest} to NOT be major update"
            )

    def test_is_major_version_update_invalid_versions(self, dependency_monitor):
        """Test major version update detection with invalid version strings."""
        test_cases = [
            ("", "2.0.0"),
            ("1.0.0", ""),
            ("invalid", "2.0.0"),
            ("1.0.0", "invalid"),
        ]

        for current, latest in test_cases:
            result = dependency_monitor._is_major_version_update(current, latest)
            assert result is False

    def test_has_breaking_changes_true(self, dependency_monitor):
        """Test breaking changes detection for versions that likely have breaking changes."""
        test_cases = ["1.0.0", "2.5.0", "3.1.4", "10.0.0"]

        for version in test_cases:
            result = dependency_monitor._has_breaking_changes(version)
            assert result is True, f"Expected {version} to have breaking changes"

    def test_has_breaking_changes_false(self, dependency_monitor):
        """Test breaking changes detection for versions that likely don't have breaking changes."""
        test_cases = ["0.1.0", "0.68.0", "0.99.9"]

        for version in test_cases:
            result = dependency_monitor._has_breaking_changes(version)
            assert result is False, f"Expected {version} to NOT have breaking changes"

    def test_has_breaking_changes_invalid(self, dependency_monitor):
        """Test breaking changes detection for invalid versions."""
        test_cases = ["", "invalid", "1"]

        for version in test_cases:
            result = dependency_monitor._has_breaking_changes(version)
            # Should handle gracefully and return False for any invalid input
            assert result is False


class TestCacheManagement:
    """Test caching functionality for update information."""

    def test_build_cache_key(self, dependency_monitor):
        """Test cache key building."""
        key = dependency_monitor._build_cache_key("requests", "2.25.0")
        assert key == "requests_2.25.0"

    def test_is_cache_entry_valid_missing_key(self, dependency_monitor):
        """Test cache entry validation when key doesn't exist."""
        cache = {}
        current_time = time.time()

        result = dependency_monitor._is_cache_entry_valid(
            "missing_key", cache, current_time
        )
        assert result is False

    def test_is_cache_entry_valid_expired(self, dependency_monitor):
        """Test cache entry validation for expired entries."""
        current_time = time.time()
        cache = {
            "test_key": {
                "timestamp": current_time
                - 90000,  # Older than 24 hours (86400 seconds)
            }
        }

        result = dependency_monitor._is_cache_entry_valid(
            "test_key", cache, current_time
        )
        assert result is False

    def test_is_cache_entry_valid_fresh(self, dependency_monitor):
        """Test cache entry validation for fresh entries."""
        current_time = time.time()
        cache = {
            "test_key": {
                "timestamp": current_time - 3600,  # 1 hour ago, within 24 hour limit
            }
        }

        result = dependency_monitor._is_cache_entry_valid(
            "test_key", cache, current_time
        )
        assert result is True

    def test_create_major_update_from_cache(self, dependency_monitor):
        """Test creating MajorUpdate from cached data."""
        cached_data = {
            "latest_version": "2.0.0",
            "release_date": "2023-06-15T10:30:00",
            "breaking_changes": True,
        }

        update = dependency_monitor._create_major_update_from_cache(
            "fastapi", "1.0.0", cached_data
        )

        assert isinstance(update, MajorUpdate)
        assert update.package == "fastapi"
        assert update.current_version == "1.0.0"
        assert update.latest_version == "2.0.0"
        assert update.release_date == "2023-06-15T10:30:00"
        assert update.breaking_changes is True

    def test_update_cache_entry(self, dependency_monitor):
        """Test updating cache entry with latest information."""
        cache = {}
        cache_key = "test_key"
        current_time = time.time()
        latest_info = {
            "version": "2.0.0",
            "release_date": "2023-06-15",
            "breaking_changes": True,
        }

        dependency_monitor._update_cache_entry(
            cache, cache_key, current_time, True, latest_info
        )

        assert cache_key in cache
        entry = cache[cache_key]
        assert entry["timestamp"] == current_time
        assert entry["has_major_update"] is True
        assert entry["latest_version"] == "2.0.0"
        assert entry["release_date"] == "2023-06-15"
        assert entry["breaking_changes"] is True

    def test_load_update_cache_missing_file(self, dependency_monitor, tmp_path):
        """Test loading cache when file doesn't exist."""
        # Set cache file to a non-existent file in temp directory
        dependency_monitor.cache_file = (
            tmp_path / ".crackerjack" / "dependency_cache.json"
        )

        cache = dependency_monitor._load_update_cache()
        assert cache == {}

    def test_load_update_cache_success(self, dependency_monitor, tmp_path):
        """Test successful cache loading."""
        mock_cache_data = {"test_key": {"timestamp": 12345}}

        # Create a temporary cache file with data
        cache_dir = tmp_path / ".crackerjack"
        cache_dir.mkdir()
        cache_file = cache_dir / "dependency_cache.json"
        cache_file.write_text(json.dumps(mock_cache_data))

        # Set dependency monitor to use the temp cache file
        dependency_monitor.cache_file = cache_file

        cache = dependency_monitor._load_update_cache()
        assert cache == mock_cache_data

    def test_save_update_cache(self, dependency_monitor, tmp_path):
        """Test saving cache data."""
        cache_data = {"test_key": {"timestamp": 12345}}

        # Set up temp cache file path
        cache_file = tmp_path / ".crackerjack" / "dependency_cache.json"
        dependency_monitor.cache_file = cache_file

        # Save cache data
        dependency_monitor._save_update_cache(cache_data)

        # Verify file was created and contains correct data
        assert cache_file.exists()
        saved_data = json.loads(cache_file.read_text())
        assert saved_data == cache_data


class TestPyPIIntegration:
    """Test PyPI API integration for version information."""

    def test_validate_pypi_url_valid(self, dependency_monitor):
        """Test PyPI URL validation for valid URLs."""
        valid_urls = [
            "https://pypi.org/pypi/requests/json",
            "https://pypi.org/pypi/django/json",
            "https://pypi.org/pypi/flask/json",
        ]

        for url in valid_urls:
            # Should not raise exception
            dependency_monitor._validate_pypi_url(url)

    def test_validate_pypi_url_invalid(self, dependency_monitor):
        """Test PyPI URL validation for invalid URLs."""
        invalid_urls = [
            "http://pypi.org/pypi/requests/json",  # HTTP instead of HTTPS
            "https://malicious.com/pypi/requests/json",  # Wrong domain
            "ftp://pypi.org/pypi/requests/json",  # Wrong protocol
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError, match="Invalid URL scheme"):
                dependency_monitor._validate_pypi_url(url)

    def test_extract_version_info_success(self, dependency_monitor):
        """Test extracting version information from PyPI response."""
        mock_data = {
            "info": {"version": "2.0.0"},
            "releases": {"2.0.0": [{"upload_time": "2023-06-15T10:30:00"}]},
        }

        result = dependency_monitor._extract_version_info(mock_data)

        assert result is not None
        assert result["version"] == "2.0.0"
        assert result["release_date"] == "2023-06-15T10:30:00"
        assert result["breaking_changes"] is True  # Version 2.0.0 has breaking changes

    def test_extract_version_info_no_version(self, dependency_monitor):
        """Test extracting version information when no version is available."""
        mock_data = {"info": {}, "releases": {}}

        result = dependency_monitor._extract_version_info(mock_data)
        assert result is None

    def test_get_release_date_success(self, dependency_monitor):
        """Test getting release date for specific version."""
        releases = {
            "2.0.0": [{"upload_time": "2023-06-15T10:30:00"}],
            "1.0.0": [{"upload_time": "2022-01-01T00:00:00"}],
        }

        result = dependency_monitor._get_release_date(releases, "2.0.0")
        assert result == "2023-06-15T10:30:00"

    def test_get_release_date_missing_version(self, dependency_monitor):
        """Test getting release date for missing version."""
        releases = {"1.0.0": [{"upload_time": "2022-01-01T00:00:00"}]}

        result = dependency_monitor._get_release_date(releases, "2.0.0")
        assert result == ""

    def test_get_release_date_empty_releases(self, dependency_monitor):
        """Test getting release date when releases list is empty."""
        releases = {"2.0.0": []}

        result = dependency_monitor._get_release_date(releases, "2.0.0")
        assert result == ""


class TestNotificationLogic:
    """Test notification timing and logic."""

    def test_should_notify_major_updates_first_time(self, dependency_monitor):
        """Test major update notification for first time (no previous notification)."""
        with patch.object(dependency_monitor, "_load_update_cache", return_value={}):
            with patch.object(dependency_monitor, "_save_update_cache") as mock_save:
                result = dependency_monitor._should_notify_major_updates()

                assert result is True
                mock_save.assert_called_once()

    def test_should_notify_major_updates_too_recent(self, dependency_monitor):
        """Test major update notification when recent notification exists."""
        current_time = time.time()
        recent_notification = current_time - 3600  # 1 hour ago

        cache = {"last_major_notification": recent_notification}
        with patch.object(dependency_monitor, "_load_update_cache", return_value=cache):
            result = dependency_monitor._should_notify_major_updates()
            assert result is False

    def test_should_notify_major_updates_old_notification(self, dependency_monitor):
        """Test major update notification when old notification exists."""
        current_time = time.time()
        old_notification = current_time - 700000  # More than a week ago

        cache = {"last_major_notification": old_notification}
        with patch.object(dependency_monitor, "_load_update_cache", return_value=cache):
            with patch.object(dependency_monitor, "_save_update_cache") as mock_save:
                result = dependency_monitor._should_notify_major_updates()

                assert result is True
                mock_save.assert_called_once()


class TestReporting:
    """Test vulnerability and update reporting functionality."""

    def test_report_vulnerabilities(self, dependency_monitor, mock_console):
        """Test vulnerability reporting output."""
        vulnerabilities = [
            DependencyVulnerability(
                package="requests",
                installed_version="2.24.0",
                vulnerability_id="CVE-2023-1234",
                severity="HIGH",
                advisory_url="https://security.example.com",
                vulnerable_versions="<2.25.0",
                patched_version="2.25.0",
            )
        ]

        dependency_monitor._report_vulnerabilities(vulnerabilities)

        # Verify multiple print calls were made
        assert mock_console.print.call_count >= 5

        # Check that vulnerability information was printed
        print_calls = []
        for call in mock_console.print.call_args_list:
            if call[0]:  # Positional arguments exist
                print_calls.append(str(call[0][0]))
            elif "end" in call[1]:  # Keyword arguments
                print_calls.append(str(call[1]))
        vulnerability_text = " ".join(print_calls)

        assert "Security Vulnerabilities Found" in vulnerability_text
        assert "requests" in vulnerability_text
        assert "CVE-2023-1234" in vulnerability_text
        assert "HIGH" in vulnerability_text

    def test_report_major_updates(self, dependency_monitor, mock_console):
        """Test major update reporting output."""
        updates = [
            MajorUpdate(
                package="fastapi",
                current_version="0.68.0",
                latest_version="1.0.0",
                release_date="2023-06-15T10:30:00",
                breaking_changes=True,
            )
        ]

        dependency_monitor._report_major_updates(updates)

        # Verify multiple print calls were made
        assert mock_console.print.call_count >= 5

        # Check that update information was printed
        print_calls = []
        for call in mock_console.print.call_args_list:
            if call[0]:  # Positional arguments exist
                print_calls.append(str(call[0][0]))
            elif "end" in call[1]:  # Keyword arguments
                print_calls.append(str(call[1]))
        update_text = " ".join(print_calls)

        assert "Major Version Updates Available" in update_text
        assert "fastapi" in update_text
        assert "0.68.0" in update_text
        assert "1.0.0" in update_text
        assert "breaking changes" in update_text


class TestForceCheckUpdates:
    """Test forced update checking functionality."""

    def test_force_check_updates_no_pyproject(
        self, dependency_monitor, mock_console, tmp_path
    ):
        """Test forced update check when pyproject.toml doesn't exist."""
        # Create a temporary directory without pyproject.toml
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()

        # Set the dependency monitor to use the test directory
        dependency_monitor.project_root = test_dir
        dependency_monitor.pyproject_path = test_dir / "pyproject.toml"

        vulnerabilities, major_updates = dependency_monitor.force_check_updates()

        assert vulnerabilities == []
        assert major_updates == []
        mock_console.print.assert_called_with(
            "[yellow]⚠️ No pyproject.toml found[/yellow]"
        )

    def test_force_check_updates_no_dependencies(
        self, dependency_monitor, mock_console, tmp_path
    ):
        """Test forced update check when no dependencies found."""
        # Create a temporary directory with empty pyproject.toml
        test_dir = tmp_path / "test_project"
        test_dir.mkdir()
        pyproject_path = test_dir / "pyproject.toml"
        pyproject_path.write_text("[project]\nname = 'test'\n")  # No dependencies

        # Set the dependency monitor to use the test directory
        dependency_monitor.project_root = test_dir
        dependency_monitor.pyproject_path = pyproject_path

        vulnerabilities, major_updates = dependency_monitor.force_check_updates()

        assert vulnerabilities == []
        assert major_updates == []

        # Check warning message was printed
        print_calls = []
        for call in mock_console.print.call_args_list:
            if call[0]:  # Positional arguments exist
                print_calls.append(str(call[0][0]))
        messages = " ".join(print_calls)
        assert "No dependencies found" in messages

    def test_force_check_updates_success(self, dependency_monitor, mock_console):
        """Test successful forced update check."""
        mock_dependencies = {"requests": "2.24.0", "fastapi": "0.68.0"}
        mock_vulnerabilities = [
            DependencyVulnerability(
                package="requests",
                installed_version="2.24.0",
                vulnerability_id="CVE-2023-1234",
                severity="HIGH",
                advisory_url="",
                vulnerable_versions="",
                patched_version="",
            )
        ]
        mock_major_updates = [
            MajorUpdate(
                package="fastapi",
                current_version="0.68.0",
                latest_version="1.0.0",
                release_date="2023-06-15",
                breaking_changes=True,
            )
        ]

        # This test mocks all the internal methods, so Path exists doesn't matter much
        with patch.object(
            dependency_monitor, "_parse_dependencies", return_value=mock_dependencies
        ):
            with patch.object(
                dependency_monitor,
                "_check_security_vulnerabilities",
                return_value=mock_vulnerabilities,
            ):
                with patch.object(
                    dependency_monitor,
                    "_check_major_updates",
                    return_value=mock_major_updates,
                ):
                    vulnerabilities, major_updates = (
                        dependency_monitor.force_check_updates()
                    )

                    assert vulnerabilities == mock_vulnerabilities
                    assert major_updates == mock_major_updates

                    # Check progress messages were printed
                    print_calls = []
                    for call in mock_console.print.call_args_list:
                        if call[0]:  # Positional arguments exist
                            print_calls.append(str(call[0][0]))
                    messages = " ".join(print_calls)
                    assert "Parsing dependencies" in messages
                    assert "Found 2 dependencies" in messages
                    assert "Checking for security vulnerabilities" in messages
                    assert "Checking for major version updates" in messages


class TestIntegrationWorkflows:
    """Test complete workflow integration."""

    def test_run_vulnerability_tool_subprocess_failure(self, dependency_monitor):
        """Test vulnerability tool execution with subprocess failure."""
        dependencies = {"requests": "2.24.0"}
        command_template = ["uv", "run", "safety", "--file", "__TEMP_FILE__"]
        parser_func = Mock()

        with patch.object(
            dependency_monitor, "_create_requirements_file"
        ) as mock_create:
            with patch.object(
                dependency_monitor, "_execute_vulnerability_command"
            ) as mock_execute:
                with patch("pathlib.Path.unlink") as mock_unlink:
                    mock_create.return_value = "/tmp/test.txt"
                    mock_execute.side_effect = subprocess.CalledProcessError(
                        1, "safety"
                    )

                    result = dependency_monitor._run_vulnerability_tool(
                        dependencies, command_template, parser_func
                    )

                    assert result == []
                    mock_unlink.assert_called_once_with(missing_ok=True)

    def test_run_vulnerability_tool_success(self, dependency_monitor):
        """Test successful vulnerability tool execution."""
        dependencies = {"requests": "2.24.0"}
        command_template = ["uv", "run", "safety", "--file", "__TEMP_FILE__"]

        mock_vulnerabilities = [
            DependencyVulnerability(
                package="requests",
                installed_version="2.24.0",
                vulnerability_id="TEST-1",
                severity="HIGH",
                advisory_url="",
                vulnerable_versions="",
                patched_version="",
            )
        ]

        parser_func = Mock(return_value=mock_vulnerabilities)

        with patch.object(
            dependency_monitor, "_create_requirements_file"
        ) as mock_create:
            with patch.object(
                dependency_monitor, "_execute_vulnerability_command"
            ) as mock_execute:
                with patch.object(
                    dependency_monitor, "_process_vulnerability_result"
                ) as mock_process:
                    with patch("pathlib.Path.unlink") as mock_unlink:
                        mock_create.return_value = "/tmp/test.txt"
                        mock_result = Mock()
                        mock_execute.return_value = mock_result
                        mock_process.return_value = mock_vulnerabilities

                        result = dependency_monitor._run_vulnerability_tool(
                            dependencies, command_template, parser_func
                        )

                        assert result == mock_vulnerabilities
                        mock_create.assert_called_once_with(dependencies)
                        mock_execute.assert_called_once()
                        mock_process.assert_called_once_with(mock_result, parser_func)
                        mock_unlink.assert_called_once_with(missing_ok=True)

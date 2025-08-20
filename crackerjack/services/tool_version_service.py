import os
import stat
import subprocess
import time
import typing as t
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from rich.console import Console


@dataclass
class VersionInfo:
    tool_name: str
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    error: str | None = None


class ToolVersionService:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.tools_to_check = {
            "ruff": self._get_ruff_version,
            "pyright": self._get_pyright_version,
            "pre-commit": self._get_precommit_version,
            "uv": self._get_uv_version,
        }

    async def check_tool_updates(self) -> dict[str, VersionInfo]:
        results = {}

        for tool_name, version_getter in self.tools_to_check.items():
            try:
                current_version = version_getter()
                if current_version:
                    latest_version = await self._fetch_latest_version(tool_name)
                    update_available = (
                        latest_version is not None
                        and self._version_compare(current_version, latest_version) < 0
                    )

                    results[tool_name] = VersionInfo(
                        tool_name=tool_name,
                        current_version=current_version,
                        latest_version=latest_version,
                        update_available=update_available,
                    )

                    if update_available:
                        self.console.print(
                            f"[yellow]🔄 {tool_name} update available: "
                            f"{current_version} → {latest_version}[/yellow]"
                        )
                else:
                    results[tool_name] = VersionInfo(
                        tool_name=tool_name,
                        current_version="not installed",
                        error=f"{tool_name} not found or not installed",
                    )
                    self.console.print(f"[red]⚠️ {tool_name} not installed[/red]")

            except Exception as e:
                results[tool_name] = VersionInfo(
                    tool_name=tool_name,
                    current_version="unknown",
                    error=str(e),
                )
                self.console.print(f"[red]❌ Error checking {tool_name}: {e}[/red]")

        return results

    def _get_ruff_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["ruff", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_line = result.stdout.strip()
                return version_line.split()[-1] if version_line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_pyright_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["pyright", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_line = result.stdout.strip()
                return version_line.split()[-1] if version_line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_precommit_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["pre-commit", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_line = result.stdout.strip()
                return version_line.split()[-1] if version_line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _get_uv_version(self) -> str | None:
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version_line = result.stdout.strip()
                return version_line.split()[-1] if version_line else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    async def _fetch_latest_version(self, tool_name: str) -> str | None:
        try:
            pypi_urls = {
                "ruff": "https://pypi.org/pypi/ruff/json",
                "pyright": "https://pypi.org/pypi/pyright/json",
                "pre-commit": "https://pypi.org/pypi/pre-commit/json",
                "uv": "https://pypi.org/pypi/uv/json",
            }

            url = pypi_urls.get(tool_name)
            if not url:
                return None

            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("info", {}).get("version")

        except Exception:
            return None

    def _version_compare(self, current: str, latest: str) -> int:
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]

            max_len = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_len - len(current_parts)))
            latest_parts.extend([0] * (max_len - len(latest_parts)))

            for i in range(max_len):
                if current_parts[i] < latest_parts[i]:
                    return -1
                elif current_parts[i] > latest_parts[i]:
                    return 1

            return 0

        except (ValueError, AttributeError):
            return 0


class ConfigIntegrityService:
    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def check_config_integrity(self) -> bool:
        config_files = [
            ".pre-commit-config.yaml",
            "pyproject.toml",
        ]

        drift_detected = False

        for file_name in config_files:
            file_path = self.project_path / file_name
            if file_path.exists():
                if self._check_file_drift(file_path):
                    drift_detected = True

        if not self._has_required_config_sections():
            self.console.print(
                "[yellow]⚠️ Configuration missing required sections[/yellow]"
            )
            drift_detected = True

        return drift_detected

    def _check_file_drift(self, file_path: Path) -> bool:
        cache_file = self.cache_dir / f"{file_path.name}.hash"

        try:
            current_content = file_path.read_text()
            current_hash = hash(current_content)

            if cache_file.exists():
                from contextlib import suppress

                with suppress(OSError, ValueError):
                    cached_hash = int(cache_file.read_text().strip())
                    if current_hash != cached_hash:
                        self.console.print(
                            f"[yellow]⚠️ {file_path.name} has been modified manually[/yellow]"
                        )
                        return True

            cache_file.write_text(str(current_hash))
            return False

        except OSError as e:
            self.console.print(f"[red]❌ Error checking {file_path.name}: {e}[/red]")
            return False

    def _has_required_config_sections(self) -> bool:
        pyproject = self.project_path / "pyproject.toml"
        if not pyproject.exists():
            return False

        try:
            import tomllib

            with pyproject.open("rb") as f:
                config = tomllib.load(f)

            required = ["tool.ruff", "tool.pyright", "tool.pytest.ini_options"]

            for section in required:
                keys = section.split(".")
                current = config

                for key in keys:
                    if key not in current:
                        self.console.print(
                            f"[yellow]⚠️ Missing required config section: {section}[/yellow]"
                        )
                        return False
                    current = current[key]

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error parsing pyproject.toml: {e}[/red]")
            return False


class SmartSchedulingService:
    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def should_scheduled_init(self) -> bool:
        init_schedule = os.environ.get("CRACKERJACK_INIT_SCHEDULE", "weekly")

        if init_schedule == "disabled":
            return False

        if init_schedule == "weekly":
            return self._check_weekly_schedule()
        elif init_schedule == "commit-based":
            return self._check_commit_based_schedule()
        elif init_schedule == "activity-based":
            return self._check_activity_based_schedule()

        return self._check_weekly_schedule()

    def _check_weekly_schedule(self) -> bool:
        init_day = os.environ.get("CRACKERJACK_INIT_DAY", "monday")
        today = datetime.now().strftime("%A").lower()

        if today == init_day.lower():
            last_init = self._get_last_init_timestamp()
            if datetime.now() - last_init > timedelta(days=6):
                self.console.print(
                    f"[blue]📅 Weekly initialization scheduled for {init_day}[/blue]"
                )
                return True

        return False

    def _check_commit_based_schedule(self) -> bool:
        commits_since_init = self._count_commits_since_init()
        threshold = int(os.environ.get("CRACKERJACK_INIT_COMMITS", "50"))

        if commits_since_init >= threshold:
            self.console.print(
                f"[blue]📊 {commits_since_init} commits since last init "
                f"(threshold: {threshold})[/blue]"
            )
            return True

        return False

    def _check_activity_based_schedule(self) -> bool:
        if self._has_recent_activity() and self._days_since_init() >= 7:
            self.console.print(
                "[blue]⚡ Recent activity detected, initialization recommended[/blue]"
            )
            return True

        return False

    def _get_last_init_timestamp(self) -> datetime:
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"

        if timestamp_file.exists():
            from contextlib import suppress

            with suppress(OSError, ValueError):
                timestamp_str = timestamp_file.read_text().strip()
                return datetime.fromisoformat(timestamp_str)

        return datetime.now() - timedelta(days=30)

    def record_init_timestamp(self) -> None:
        timestamp_file = self.cache_dir / f"{self.project_path.name}.init_timestamp"
        try:
            timestamp_file.write_text(datetime.now().isoformat())
        except OSError as e:
            self.console.print(
                f"[yellow]⚠️ Could not record init timestamp: {e}[/yellow]"
            )

    def _count_commits_since_init(self) -> int:
        since_date = self._get_last_init_timestamp().strftime("%Y-%m-%d")

        try:
            result = subprocess.run(
                ["git", "log", f"--since={since_date}", "--oneline"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode == 0:
                return len([line for line in result.stdout.strip().split("\n") if line])

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return 0

    def _has_recent_activity(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--since=24.hours", "--oneline"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            return result.returncode == 0 and bool(result.stdout.strip())

        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _days_since_init(self) -> int:
        last_init = self._get_last_init_timestamp()
        return (datetime.now() - last_init).days


class UnifiedConfigurationService:
    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.config_cache = {}
        self.project_type = self._detect_project_type()

    def _detect_project_type(self) -> str:
        if (self.project_path / "pyproject.toml").exists():
            return "python"
        elif (self.project_path / "package.json").exists():
            return "node"
        elif (self.project_path / "Cargo.toml").exists():
            return "rust"
        elif (self.project_path / "go.mod").exists():
            return "go"

        return "generic"

    def get_unified_config(self) -> dict[str, t.Any]:
        if "unified_config" in self.config_cache:
            return self.config_cache["unified_config"]

        base_config = {
            "project_type": self.project_type,
            "project_path": str(self.project_path),
            "tools": {},
            "hooks": {},
            "testing": {},
            "quality": {},
        }

        if self.project_type == "python":
            base_config.update(self._load_python_config())
        elif self.project_type == "node":
            base_config.update(self._load_node_config())
        elif self.project_type == "rust":
            base_config.update(self._load_rust_config())
        elif self.project_type == "go":
            base_config.update(self._load_go_config())

        self.config_cache["unified_config"] = base_config
        return base_config

    def _load_python_config(self) -> dict[str, t.Any]:
        pyproject = self.project_path / "pyproject.toml"
        config = {"tools": {}, "hooks": {}, "testing": {}, "quality": {}}

        if pyproject.exists():
            try:
                import tomllib

                with pyproject.open("rb") as f:
                    toml_data = tomllib.load(f)

                if "tool" in toml_data:
                    tool_data = toml_data["tool"]

                    if "ruff" in tool_data:
                        config["tools"]["ruff"] = {
                            "enabled": True,
                            "config": tool_data["ruff"],
                            "priority": "high",
                        }

                    if "pyright" in tool_data:
                        config["tools"]["pyright"] = {
                            "enabled": True,
                            "config": tool_data["pyright"],
                            "priority": "high",
                        }

                    if "pytest" in tool_data:
                        config["testing"]["pytest"] = {
                            "enabled": True,
                            "config": tool_data["pytest"],
                            "priority": "critical",
                        }

                    for tool in (
                        "bandit",
                        "vulture",
                        "complexipy",
                        "creosote",
                        "refurb",
                    ):
                        if tool in tool_data:
                            config["quality"][tool] = {
                                "enabled": True,
                                "config": tool_data[tool],
                                "priority": "medium",
                            }

            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️ Error loading pyproject.toml: {e}[/yellow]"
                )

        return config

    def _load_node_config(self) -> dict[str, t.Any]:
        config = {"tools": {}, "hooks": {}, "testing": {}, "quality": {}}

        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                import json

                with package_json.open() as f:
                    pkg_data = json.load(f)

                if "scripts" in pkg_data:
                    scripts = pkg_data["scripts"]
                    if "lint" in scripts:
                        config["quality"]["eslint"] = {
                            "enabled": True,
                            "priority": "high",
                        }
                    if "test" in scripts:
                        config["testing"]["jest"] = {
                            "enabled": True,
                            "priority": "critical",
                        }
                    if "format" in scripts:
                        config["tools"]["prettier"] = {
                            "enabled": True,
                            "priority": "medium",
                        }

            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️ Error loading package.json: {e}[/yellow]"
                )

        return config

    def _load_rust_config(self) -> dict[str, t.Any]:
        config = {"tools": {}, "hooks": {}, "testing": {}, "quality": {}}

        cargo_toml = self.project_path / "Cargo.toml"
        if cargo_toml.exists():
            config["tools"]["cargo"] = {"enabled": True, "priority": "critical"}
            config["quality"]["clippy"] = {"enabled": True, "priority": "high"}
            config["tools"]["rustfmt"] = {"enabled": True, "priority": "medium"}
            config["testing"]["cargo_test"] = {"enabled": True, "priority": "critical"}

        return config

    def _load_go_config(self) -> dict[str, t.Any]:
        config = {"tools": {}, "hooks": {}, "testing": {}, "quality": {}}

        go_mod = self.project_path / "go.mod"
        if go_mod.exists():
            config["tools"]["go"] = {"enabled": True, "priority": "critical"}
            config["quality"]["golint"] = {"enabled": True, "priority": "high"}
            config["tools"]["gofmt"] = {"enabled": True, "priority": "medium"}
            config["testing"]["go_test"] = {"enabled": True, "priority": "critical"}

        return config

    def get_tool_config(self, tool_name: str) -> dict[str, t.Any] | None:
        unified_config = self.get_unified_config()

        for section in ("tools", "quality", "testing", "hooks"):
            if tool_name in unified_config.get(section, {}):
                return unified_config[section][tool_name]

        return None

    def update_tool_config(
        self, tool_name: str, section: str, config: dict[str, t.Any]
    ) -> bool:
        try:
            unified_config = self.get_unified_config()

            if section not in unified_config:
                unified_config[section] = {}

            unified_config[section][tool_name] = config

            if self.project_type == "python":
                return self._update_python_config(tool_name, section, config)

            self.console.print(f"[green]✅ Updated {tool_name} configuration[/green]")
            return True

        except Exception as e:
            self.console.print(
                f"[red]❌ Failed to update {tool_name} config: {e}[/red]"
            )
            return False

    def _update_python_config(
        self, tool_name: str, section: str, config: dict[str, t.Any]
    ) -> bool:
        pyproject = self.project_path / "pyproject.toml"

        if not pyproject.exists():
            return False

        try:
            import tomllib

            import tomli_w

            with pyproject.open("rb") as f:
                toml_data = tomllib.load(f)

            if "tool" not in toml_data:
                toml_data["tool"] = {}

            if "config" in config:
                toml_data["tool"][tool_name] = config["config"]

            with pyproject.open("wb") as f:
                tomli_w.dump(toml_data, f)

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Failed to update pyproject.toml: {e}[/red]")
            return False

    def validate_configuration(self) -> dict[str, t.Any]:
        unified_config = self.get_unified_config()
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "suggestions": [],
        }

        required_tools = self._get_required_tools_for_project_type()

        for tool in required_tools:
            tool_config = self.get_tool_config(tool)

            if not tool_config:
                validation_results["errors"].append(
                    f"Required tool {tool} not configured"
                )
                validation_results["valid"] = False
            elif not tool_config.get("enabled", False):
                validation_results["warnings"].append(
                    f"Tool {tool} is configured but disabled"
                )

        conflicts = self._check_configuration_conflicts(unified_config)
        validation_results["warnings"].extend(conflicts)

        suggestions = self._get_optimization_suggestions(unified_config)
        validation_results["suggestions"].extend(suggestions)

        return validation_results

    def _get_required_tools_for_project_type(self) -> dict[str, dict[str, t.Any]]:
        if self.project_type == "python":
            return {
                "ruff": {"priority": "high", "reason": "Python linting and formatting"},
                "pyright": {"priority": "high", "reason": "Type checking"},
                "pytest": {"priority": "critical", "reason": "Testing framework"},
            }
        elif self.project_type == "node":
            return {
                "eslint": {"priority": "high", "reason": "JavaScript linting"},
                "jest": {"priority": "critical", "reason": "Testing framework"},
            }
        elif self.project_type == "rust":
            return {
                "cargo": {"priority": "critical", "reason": "Build system"},
                "clippy": {"priority": "high", "reason": "Linting"},
            }
        elif self.project_type == "go":
            return {
                "go": {"priority": "critical", "reason": "Build system"},
                "golint": {"priority": "high", "reason": "Linting"},
            }

        return {}

    def _check_configuration_conflicts(self, config: dict[str, t.Any]) -> list[str]:
        conflicts = []

        formatters = []
        for section in ("tools", "quality"):
            for tool_name, tool_config in config.get(section, {}).items():
                if tool_name in (
                    "ruff",
                    "black",
                    "autopep8",
                    "prettier",
                    "rustfmt",
                    "gofmt",
                ):
                    if tool_config.get("enabled", False):
                        formatters.append(tool_name)

        if len(formatters) > 1:
            conflicts.append(f"Multiple formatters enabled: {', '.join(formatters)}")

        return conflicts

    def _get_optimization_suggestions(self, config: dict[str, t.Any]) -> list[str]:
        suggestions = []

        if self.project_type == "python":
            quality_tools = config.get("quality", {})
            if not quality_tools.get("bandit", {}).get("enabled", False):
                suggestions.append("Consider enabling Bandit for security scanning")
            if not quality_tools.get("vulture", {}).get("enabled", False):
                suggestions.append("Consider enabling Vulture for dead code detection")

        return suggestions


class EnhancedErrorCategorizationService:
    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.error_patterns = self._initialize_error_patterns()
        self.error_history = []

    def _initialize_error_patterns(self) -> dict[str, dict[str, t.Any]]:
        return {
            "import_error": {
                "patterns": [
                    r"ModuleNotFoundError: No module named '(.+ )'",
                    r"ImportError: cannot import name '(.+ )' from '(.+ )'",
                    r"ImportError: No module named (.+ )",
                ],
                "category": "dependency",
                "severity": "high",
                "auto_fixable": True,
                "priority": 1,
                "description": "Missing dependencies or import issues",
            },
            "syntax_error": {
                "patterns": [
                    r"SyntaxError: (.+ )",
                    r"IndentationError: (.+ )",
                    r"TabError: (.+ )",
                ],
                "category": "syntax",
                "severity": "critical",
                "auto_fixable": True,
                "priority": 1,
                "description": "Python syntax and indentation errors",
            },
            "type_error": {
                "patterns": [
                    r"error: (.+ ) \[(.+ )\]",
                    r"TypeError: (.+ )",
                    r"Argument .+ to .+ has incompatible type",
                ],
                "category": "typing",
                "severity": "medium",
                "auto_fixable": True,
                "priority": 2,
                "description": "Type checking and annotation issues",
            },
            "security_issue": {
                "patterns": [
                    r"B\d+ : (.+ )",
                    r"Security issue: (.+ )",
                    r"Vulnerability: (.+ )",
                ],
                "category": "security",
                "severity": "high",
                "auto_fixable": False,
                "priority": 1,
                "description": "Security vulnerabilities requiring attention",
            },
            "complexity_violation": {
                "patterns": [
                    r"C901 (.+ ) is too complex \((\d+ )\)",
                    r"Cognitive complexity of (\d+ ) exceeds maximum of (\d+ )",
                    r"Function .+ has complexity (\d+ )",
                ],
                "category": "quality",
                "severity": "medium",
                "auto_fixable": True,
                "priority": 3,
                "description": "Code complexity violations",
            },
            "dead_code": {
                "patterns": [
                    r"unused import '(.+ )'",
                    r"'(.+ )' imported but unused",
                    r"unused variable '(.+ )'",
                    r"unused function '(.+ )'",
                ],
                "category": "quality",
                "severity": "low",
                "auto_fixable": True,
                "priority": 4,
                "description": "Unused imports, variables, and functions",
            },
            "test_failure": {
                "patterns": [
                    r"FAILED (.+ ) - (.+ )",
                    r"AssertionError: (.+ )",
                    r"pytest.main\(\) returned (.+ )",
                    r"(\d+ ) failed, (\d+ ) passed",
                ],
                "category": "testing",
                "severity": "high",
                "auto_fixable": False,
                "priority": 2,
                "description": "Test failures requiring investigation",
            },
            "formatting_issue": {
                "patterns": [
                    r"would reformat (.+ )",
                    r"reformatted (.+ )",
                    r"line too long \((\d+ ) > (\d+ ) characters\)",
                    r"trailing whitespace",
                ],
                "category": "formatting",
                "severity": "low",
                "auto_fixable": True,
                "priority": 5,
                "description": "Code formatting and style issues",
            },
            "dependency_conflict": {
                "patterns": [
                    r"(.+ ) \((.+ )\) conflicts with (.+ ) \((.+ )\)",
                    r"dependency conflict: (.+ )",
                    r"version conflict: (.+ )",
                ],
                "category": "dependency",
                "severity": "high",
                "auto_fixable": False,
                "priority": 2,
                "description": "Dependency version conflicts",
            },
        }

    def categorize_errors(self, error_text: str | list[str]) -> list[dict[str, t.Any]]:
        if isinstance(error_text, str):
            error_lines = error_text.split("\n")
        else:
            error_lines = error_text

        categorized_errors = []

        for line in error_lines:
            if not line.strip():
                continue

            error_info = self._classify_error_line(line)
            if error_info:
                categorized_errors.append(error_info)

        import operator

        categorized_errors.sort(key=operator.itemgetter("priority", "severity_score"))

        self.error_history.extend(categorized_errors)

        return categorized_errors

    def _classify_error_line(self, line: str) -> dict[str, t.Any] | None:
        import re

        for error_type, pattern_info in self.error_patterns.items():
            for pattern in pattern_info["patterns"]:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    severity_score = self._get_severity_score(pattern_info["severity"])

                    return {
                        "type": error_type,
                        "raw_line": line,
                        "matched_groups": match.groups(),
                        "category": pattern_info["category"],
                        "severity": pattern_info["severity"],
                        "severity_score": severity_score,
                        "auto_fixable": pattern_info["auto_fixable"],
                        "priority": pattern_info["priority"],
                        "description": pattern_info["description"],
                        "pattern_matched": pattern,
                        "suggested_fix": self._suggest_fix(
                            error_type, match.groups(), line
                        ),
                    }

        return {
            "type": "unknown",
            "raw_line": line,
            "matched_groups": (),
            "category": "unknown",
            "severity": "medium",
            "severity_score": 2,
            "auto_fixable": False,
            "priority": 3,
            "description": "Unclassified error requiring manual review",
            "pattern_matched": None,
            "suggested_fix": None,
        }

    def _get_severity_score(self, severity: str) -> int:
        return {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(severity, 3)

    def _suggest_fix(
        self, error_type: str, groups: tuple[str, ...], line: str
    ) -> str | None:
        if error_type == "import_error" and groups:
            missing_module = groups[0]
            return f"Add '{missing_module}' to pyproject.toml dependencies or install with: uv add {missing_module}"

        elif error_type == "syntax_error":
            return "Review Python syntax, check for missing colons, parentheses, or indentation issues"

        elif error_type == "type_error" and groups:
            return f"Add type annotations or fix type mismatch: {groups[0] if groups else 'review types'}"

        elif error_type == "dead_code" and groups:
            unused_item = groups[0]
            return f"Remove unused {unused_item} or add # noqa comment if intentionally unused"

        elif error_type == "complexity_violation":
            return "Refactor function into smaller helper methods to reduce cognitive complexity"

        elif error_type == "formatting_issue":
            return "Run 'ruff format' or fix formatting manually"

        elif error_type == "security_issue":
            return "Review security issue and apply recommended fixes from Bandit documentation"

        elif error_type == "test_failure":
            return (
                "Debug test failure by examining assertion details and test environment"
            )

        return None

    def get_error_summary(self, errors: list[dict[str, t.Any]]) -> dict[str, t.Any]:
        if not errors:
            return {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "auto_fixable_count": 0,
                "critical_issues": [],
                "recommended_actions": [],
            }

        by_category = {}
        by_severity = {}
        auto_fixable_count = 0
        critical_issues = []

        for error in errors:
            category = error["category"]
            by_category[category] = by_category.get(category, 0) + 1

            severity = error["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1

            if error["auto_fixable"]:
                auto_fixable_count += 1

            if error["severity"] in ("critical", "high"):
                critical_issues.append(
                    {
                        "type": error["type"],
                        "description": error["description"],
                        "line": error["raw_line"][:100] + "..."
                        if len(error["raw_line"]) > 100
                        else error["raw_line"],
                    }
                )

        recommended_actions = self._generate_recommended_actions(
            by_category, by_severity, auto_fixable_count
        )

        return {
            "total_errors": len(errors),
            "by_category": by_category,
            "by_severity": by_severity,
            "auto_fixable_count": auto_fixable_count,
            "auto_fixable_percentage": round(
                (auto_fixable_count / len(errors)) * 100, 1
            ),
            "critical_issues": critical_issues[:5],
            "recommended_actions": recommended_actions,
        }

    def _generate_recommended_actions(
        self,
        by_category: dict[str, int],
        by_severity: dict[str, int],
        auto_fixable: int,
    ) -> list[str]:
        actions = []

        critical_count = by_severity.get("critical", 0) + by_severity.get("high", 0)
        if critical_count > 0:
            actions.append(
                f"🚨 Address {critical_count} critical / high severity issues first"
            )

        if by_category.get("dependency", 0) > 0:
            actions.append(
                "📦 Review dependency issues - check pyproject.toml and run 'uv sync'"
            )

        if by_category.get("security", 0) > 0:
            actions.append(
                "🔒 Security issues require immediate attention - review Bandit findings"
            )

        if by_category.get("testing", 0) > 0:
            actions.append(
                "🧪 Test failures need debugging - check test environment and assertions"
            )

        if by_category.get("typing", 0) > 0:
            actions.append(
                "🔤 Type issues can be auto - fixed - consider running type annotation tools"
            )

        if auto_fixable > 0:
            actions.append(
                f"⚡ {auto_fixable} errors can be auto - fixed with AI agent mode"
            )

        if by_category.get("quality", 0) > 3:
            actions.append(
                "🔄 Multiple quality issues - consider refactoring complex functions"
            )

        return actions

    def print_error_report(self, errors: list[dict[str, t.Any]]) -> None:
        if not errors:
            self.console.print("[green]✅ No errors found ! [/green]")
            return

        summary = self.get_error_summary(errors)

        self.console.print("\n[bold red]📊 Error Analysis Report[/bold red]")
        self.console.print(f"Total Errors: {summary['total_errors']}")
        self.console.print(
            f"Auto - fixable: {summary['auto_fixable_count']} ({summary['auto_fixable_percentage']} % )"
        )

        self.console.print("\n[bold]By Severity: [/bold]")
        for severity, count in summary["by_severity"].items():
            severity_color = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "dim",
            }.get(severity, "white")
            self.console.print(
                f" [{severity_color}]{severity.title()}: {count}[ / {severity_color}]"
            )

        self.console.print("\n[bold]By Category: [/bold]")
        for category, count in summary["by_category"].items():
            self.console.print(f" {category.title()}: {count}")

        if summary["critical_issues"]:
            self.console.print("\n[bold red]Critical Issues: [/bold red]")
            for issue in summary["critical_issues"]:
                self.console.print(f" • {issue['description']}")
                self.console.print(f" [dim]{issue['line']}[/dim]")

        if summary["recommended_actions"]:
            self.console.print("\n[bold cyan]Recommended Actions: [ / bold cyan]")
            for action in summary["recommended_actions"]:
                self.console.print(f" {action}")


class GitHookService:
    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.hooks_dir = project_path / ".git" / "hooks"

    def install_pre_commit_hook(self, force: bool = False) -> bool:
        if not self.hooks_dir.exists():
            self.console.print("[yellow]⚠️ Git hooks directory not found[/yellow]")
            return False

        hook_path = self.hooks_dir / "pre-commit"

        if hook_path.exists() and not force:
            self.console.print(
                "[yellow]⚠️ pre-commit hook already exists (use force = True to overwrite)[/yellow]"
            )
            return False

        hook_script = self._create_pre_commit_hook_script()

        try:
            hook_path.write_text(hook_script)

            hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

            self.console.print(
                "[green]✅ pre-commit hook installed successfully[/green]"
            )
            return True

        except OSError as e:
            self.console.print(
                f"[red]❌ Failed to install pre-commit hook: {e}[/red]"
            )
            return False

    def check_init_needed_quick(self) -> int:
        if not (self.project_path / "pyproject.toml").exists():
            return 1

        pre_commit = self.project_path / ".pre-commit-config.yaml"
        if pre_commit.exists():
            age_days = (time.time() - pre_commit.stat().st_mtime) / 86400
            if age_days > 30:
                return 1

        return 0

    def _create_pre_commit_hook_script(self) -> str:
        return """#!/bin/bash

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "⚠️ Python not found in PATH"
    exit 0
fi

if ! $PYTHON -c "import crackerjack" >/dev/null 2>&1; then
    exit 0
fi

$PYTHON -c "
import sys
from pathlib import Path
from crackerjack.services.tool_version_service import GitHookService
from rich.console import Console

console = Console()
service = GitHookService(console, Path.cwd())
exit_code = service.check_init_needed_quick()

if exit_code == 1:
    console.print('[yellow]⚠️ Project initialization needed![/yellow]')
    console.print('[blue]Run: python -m crackerjack --init[/blue]')
    console.print('[dim]Or commit with --no-verify to skip this check[/dim]')

sys.exit(exit_code)
"

"""

    def remove_pre_commit_hook(self) -> bool:
        hook_path = self.hooks_dir / "pre-commit"

        if not hook_path.exists():
            self.console.print("[yellow]⚠️ pre-commit hook does not exist[/yellow]")
            return False

        try:
            content = hook_path.read_text()
            if "Crackerjack pre-commit hook" in content:
                hook_path.unlink()
                self.console.print(
                    "[green]✅ Crackerjack pre-commit hook removed[/green]"
                )
                return True
            else:
                self.console.print(
                    "[yellow]⚠️ pre-commit hook exists but is not a Crackerjack hook[/yellow]"
                )
                return False

        except OSError as e:
            self.console.print(
                f"[red]❌ Failed to remove pre-commit hook: {e}[/red]"
            )
            return False

    def is_hook_installed(self) -> bool:
        hook_path = self.hooks_dir / "pre-commit"

        if not hook_path.exists():
            return False

        try:
            content = hook_path.read_text()
            return "Crackerjack pre-commit hook" in content
        except OSError:
            return False

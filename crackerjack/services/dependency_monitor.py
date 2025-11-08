import json
import subprocess
import tempfile
import time
import tomllib
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import FileSystemInterface


@dataclass
class DependencyVulnerability:
    package: str
    installed_version: str
    vulnerability_id: str
    severity: str
    advisory_url: str
    vulnerable_versions: str
    patched_version: str


@dataclass
class MajorUpdate:
    package: str
    current_version: str
    latest_version: str
    release_date: str
    breaking_changes: bool


class DependencyMonitorService:
    def __init__(
        self,
        filesystem: FileSystemInterface,
        console: Console | None = None,
    ) -> None:
        self.filesystem = filesystem
        self.console = console or Console()
        self.project_root = Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self.cache_file = self.project_root / ".crackerjack" / "dependency_cache.json"

    def check_dependency_updates(self) -> bool:
        if not self.pyproject_path.exists():
            return False

        dependencies = self._parse_dependencies()
        if not dependencies:
            return False

        vulnerabilities = self._check_security_vulnerabilities(dependencies)
        major_updates = self._check_major_updates(dependencies)

        if vulnerabilities:
            self._report_vulnerabilities(vulnerabilities)
            return True

        if major_updates and self._should_notify_major_updates():
            self._report_major_updates(major_updates)
            return True

        return False

    def _parse_dependencies(self) -> dict[str, str]:
        try:
            with self.pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            dependencies: dict[str, str] = {}
            project_data = data.get("project", {})

            self._extract_main_dependencies(project_data, dependencies)
            self._extract_optional_dependencies(project_data, dependencies)

            return dependencies

        except Exception as e:
            self.console.print(
                f"[yellow]Warning: Failed to parse pyproject.toml: {e}[/ yellow]",
            )
            return {}

    def _extract_main_dependencies(
        self,
        project_data: dict[str, t.Any],
        dependencies: dict[str, str],
    ) -> None:
        if "dependencies" not in project_data:
            return

        for dep in project_data["dependencies"]:
            name, version = self._parse_dependency_spec(dep)
            if name and version:
                dependencies[name] = version

    def _extract_optional_dependencies(
        self,
        project_data: dict[str, t.Any],
        dependencies: dict[str, str],
    ) -> None:
        if "optional-dependencies" not in project_data:
            return

        for group_deps in project_data["optional-dependencies"].values():
            for dep in group_deps:
                name, version = self._parse_dependency_spec(dep)
                if name and version:
                    dependencies[name] = version

    def _parse_dependency_spec(self, spec: str) -> tuple[str | None, str | None]:
        if not spec or spec.startswith("-"):
            return None, None

        for operator in ("> =", "< =", "= =", "~=", "! =", ">", "<"):
            if operator in spec:
                parts = spec.split(operator, 1)
                if len(parts) == 2:
                    package = parts[0].strip()
                    version = parts[1].strip()
                    return package, version

        return spec.strip(), "latest"

    def _check_security_vulnerabilities(
        self,
        dependencies: dict[str, str],
    ) -> list[DependencyVulnerability]:
        vulnerabilities: list[DependencyVulnerability] = []

        safety_vulns = self._check_with_safety(dependencies)
        vulnerabilities.extend(safety_vulns)

        if not vulnerabilities:
            pip_audit_vulns = self._check_with_pip_audit(dependencies)
            vulnerabilities.extend(pip_audit_vulns)

        return vulnerabilities

    def _check_with_safety(
        self,
        dependencies: dict[str, str],
    ) -> list[DependencyVulnerability]:
        cmd = ["uv", "run", "safety", "check", "--file", "__TEMP_FILE__", "--json"]
        return self._run_vulnerability_tool(
            dependencies,
            cmd,
            self._parse_safety_output,
        )

    def _check_with_pip_audit(
        self,
        dependencies: dict[str, str],
    ) -> list[DependencyVulnerability]:
        cmd = [
            "uv",
            "run",
            "pip-audit",
            "--requirement",
            "__TEMP_FILE__",
            "--format",
            "json",
        ]
        return self._run_vulnerability_tool(
            dependencies,
            cmd,
            self._parse_pip_audit_output,
        )

    def _run_vulnerability_tool(
        self,
        dependencies: dict[str, str],
        command_template: list[str],
        parser_func: t.Callable[[t.Any], list[DependencyVulnerability]],
    ) -> list[DependencyVulnerability]:
        try:
            temp_file = self._create_requirements_file(dependencies)
            try:
                result = self._execute_vulnerability_command(
                    command_template,
                    temp_file,
                )
                return self._process_vulnerability_result(result, parser_func)
            finally:
                Path(temp_file).unlink(missing_ok=True)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            Exception,
        ):
            return []

    def _create_requirements_file(self, dependencies: dict[str, str]) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for package, version in dependencies.items():
                if version != "latest":
                    f.write(f"{package}= ={version}\n")
                else:
                    f.write(f"{package}\n")
            return f.name

    def _execute_vulnerability_command(
        self,
        command_template: list[str],
        temp_file: str,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [part.replace("__TEMP_FILE__", temp_file) for part in command_template]
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _process_vulnerability_result(
        self,
        result: subprocess.CompletedProcess[str],
        parser_func: t.Callable[[t.Any], list[DependencyVulnerability]],
    ) -> list[DependencyVulnerability]:
        if result.returncode == 0:
            return []

        if result.stdout:
            data = json.loads(result.stdout)
            return parser_func(data)

        return []

    def _parse_safety_output(self, safety_data: t.Any) -> list[DependencyVulnerability]:
        vulnerabilities: list[DependencyVulnerability] = []

        with suppress(Exception):
            for vuln in safety_data:
                vulnerabilities.append(
                    DependencyVulnerability(
                        package=vuln.get("package", ""),
                        installed_version=vuln.get("installed_version", ""),
                        vulnerability_id=vuln.get("vulnerability_id", ""),
                        severity=vuln.get("severity", "unknown"),
                        advisory_url=vuln.get("more_info_url", ""),
                        vulnerable_versions=vuln.get("vulnerable_spec", ""),
                        patched_version=vuln.get("analyzed_version", ""),
                    ),
                )

        return vulnerabilities

    def _parse_pip_audit_output(
        self,
        audit_data: t.Any,
    ) -> list[DependencyVulnerability]:
        vulnerabilities: list[DependencyVulnerability] = []

        with suppress(Exception):
            for vuln in audit_data.get("vulnerabilities", []):
                package = vuln.get("package", {})
                vulnerabilities.append(
                    DependencyVulnerability(
                        package=package.get("name", ""),
                        installed_version=package.get("version", ""),
                        vulnerability_id=vuln.get("id", ""),
                        severity=vuln.get("severity", "unknown"),
                        advisory_url=vuln.get("link", ""),
                        vulnerable_versions=vuln.get("vulnerable_ranges", ""),
                        patched_version=vuln.get("fix_versions", [""])[0],
                    ),
                )

        return vulnerabilities

    def _check_major_updates(self, dependencies: dict[str, str]) -> list[MajorUpdate]:
        major_updates: list[MajorUpdate] = []
        cache = self._load_update_cache()
        current_time = time.time()

        for package, current_version in dependencies.items():
            if current_version == "latest":
                continue

            update = self._check_package_major_update(
                package,
                current_version,
                cache,
                current_time,
            )
            if update:
                major_updates.append(update)

        self._save_update_cache(cache)
        return major_updates

    def _check_package_major_update(
        self,
        package: str,
        current_version: str,
        cache: dict[str, t.Any],
        current_time: float,
    ) -> MajorUpdate | None:
        cache_key = self._build_cache_key(package, current_version)

        cached_update = self._get_cached_major_update(
            cache_key,
            cache,
            current_time,
            package,
            current_version,
        )
        if cached_update is not None:
            return cached_update

        return self._fetch_and_cache_update_info(
            package,
            current_version,
            cache_key,
            cache,
            current_time,
        )

    def _build_cache_key(self, package: str, current_version: str) -> str:
        return f"{package}_{current_version}"

    def _get_cached_major_update(
        self,
        cache_key: str,
        cache: dict[str, t.Any],
        current_time: float,
        package: str,
        current_version: str,
    ) -> MajorUpdate | None:
        if not self._is_cache_entry_valid(cache_key, cache, current_time):
            return None

        cached_data = cache[cache_key]
        if not cached_data["has_major_update"]:
            return None

        return self._create_major_update_from_cache(
            package,
            current_version,
            cached_data,
        )

    def _is_cache_entry_valid(
        self,
        cache_key: str,
        cache: dict[str, t.Any],
        current_time: float,
    ) -> bool:
        if cache_key not in cache:
            return False

        cached_data = cache[cache_key]
        cache_age = current_time - cached_data["timestamp"]
        return cache_age < 86400

    def _create_major_update_from_cache(
        self,
        package: str,
        current_version: str,
        cached_data: dict[str, t.Any],
    ) -> MajorUpdate:
        return MajorUpdate(
            package=package,
            current_version=current_version,
            latest_version=cached_data["latest_version"],
            release_date=cached_data["release_date"],
            breaking_changes=cached_data["breaking_changes"],
        )

    def _fetch_and_cache_update_info(
        self,
        package: str,
        current_version: str,
        cache_key: str,
        cache: dict[str, t.Any],
        current_time: float,
    ) -> MajorUpdate | None:
        latest_info = self._get_latest_version_info(package)
        if not latest_info:
            return None

        has_major_update = self._is_major_version_update(
            current_version,
            latest_info["version"],
        )

        self._update_cache_entry(
            cache,
            cache_key,
            current_time,
            has_major_update,
            latest_info,
        )

        return self._create_major_update_if_needed(
            package,
            current_version,
            latest_info,
            has_major_update,
        )

    def _create_major_update_if_needed(
        self,
        package: str,
        current_version: str,
        latest_info: dict[str, t.Any],
        has_major_update: bool,
    ) -> MajorUpdate | None:
        if not has_major_update:
            return None

        return MajorUpdate(
            package=package,
            current_version=current_version,
            latest_version=latest_info["version"],
            release_date=latest_info["release_date"],
            breaking_changes=latest_info["breaking_changes"],
        )

    def _update_cache_entry(
        self,
        cache: dict[str, t.Any],
        cache_key: str,
        current_time: float,
        has_major_update: bool,
        latest_info: dict[str, t.Any],
    ) -> None:
        cache[cache_key] = {
            "timestamp": current_time,
            "has_major_update": has_major_update,
            "latest_version": latest_info["version"],
            "release_date": latest_info["release_date"],
            "breaking_changes": latest_info["breaking_changes"],
        }

    def _get_latest_version_info(self, package: str) -> dict[str, t.Any] | None:
        try:
            data = self._fetch_pypi_data(package)
            return self._extract_version_info(data)
        except Exception:
            return None

    def _fetch_pypi_data(self, package: str) -> dict[str, t.Any]:
        from urllib.parse import urlparse

        import requests

        url = f"https: //pypi.org/pypi/{package}/json"
        self._validate_pypi_url(url)

        parsed = urlparse(url)

        if parsed.scheme != "https" or parsed.netloc != "pypi.org":
            msg = f"Invalid URL: only https: //pypi.org URLs are allowed, got {url}"
            raise ValueError(msg)

        response = requests.get(url, timeout=10, verify=True)
        response.raise_for_status()
        return t.cast(dict[str, t.Any], response.json())

    def _validate_pypi_url(self, url: str) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(url)

        if parsed.scheme != "https":
            msg = f"Invalid URL scheme '{parsed.scheme}': only HTTPS is allowed"
            raise ValueError(msg)

        if parsed.netloc != "pypi.org":
            msg = f"Invalid hostname '{parsed.netloc}': only pypi.org is allowed"
            raise ValueError(msg)

        if not parsed.path.startswith("/pypi/") or not parsed.path.endswith("/json"):
            msg = f"Invalid PyPI API path: {parsed.path}"
            raise ValueError(msg)

    def _extract_version_info(self, data: dict[str, t.Any]) -> dict[str, t.Any] | None:
        info = data.get("info", {})
        releases = data.get("releases", {})

        latest_version = info.get("version", "")
        if not latest_version:
            return None

        release_date = self._get_release_date(releases, latest_version)
        breaking_changes = self._has_breaking_changes(latest_version)

        return {
            "version": latest_version,
            "release_date": release_date,
            "breaking_changes": breaking_changes,
        }

    def _get_release_date(self, releases: dict[str, t.Any], version: str) -> str:
        release_info = releases.get(version, [])
        if release_info:
            return release_info[0].get("upload_time", "")
        return ""

    def _has_breaking_changes(self, version: str) -> bool:
        return version.split(".")[0] != "0" if "." in version else False

    def _is_major_version_update(self, current: str, latest: str) -> bool:
        with suppress(ValueError, IndexError):
            current_parts = current.split(".")
            latest_parts = latest.split(".")

            if current_parts and latest_parts:
                current_major = int(current_parts[0])
                latest_major = int(latest_parts[0])
                return latest_major > current_major

        return False

    def _should_notify_major_updates(self) -> bool:
        cache = self._load_update_cache()
        last_major_notification = cache.get("last_major_notification", 0)
        current_time = time.time()

        if current_time - last_major_notification > 604800:
            cache["last_major_notification"] = current_time
            self._save_update_cache(cache)
            return True

        return False

    def _load_update_cache(self) -> dict[str, t.Any]:
        with suppress(Exception):
            if self.cache_file.exists():
                with self.cache_file.open() as f:
                    return t.cast(dict[str, t.Any], json.load(f))
        return {}

    def _save_update_cache(self, cache: dict[str, t.Any]) -> None:
        with suppress(Exception):
            self.cache_file.parent.mkdir(exist_ok=True)
            with self.cache_file.open("w") as f:
                json.dump(cache, f, indent=2)

    def _report_vulnerabilities(
        self,
        vulnerabilities: list[DependencyVulnerability],
    ) -> None:
        self.console.print(
            "\n[bold red]🚨 Security Vulnerabilities Found ![/ bold red]"
        )
        self.console.print(
            "[red]Please update the following packages immediately: [/ red]\n",
        )

        for vuln in vulnerabilities:
            self.console.print(f"[red]• {vuln.package} {vuln.installed_version}[/ red]")
            self.console.print(
                f" [dim]Vulnerability ID: {vuln.vulnerability_id}[/ dim]"
            )
            self.console.print(f" [dim]Severity: {vuln.severity.upper()}[/ dim]")
            if vuln.patched_version:
                self.console.print(
                    f" [green]Fix available: {vuln.patched_version}[/ green]",
                )
            if vuln.advisory_url:
                self.console.print(f" [dim]More info: {vuln.advisory_url}[/ dim]")
            self.console.print()

    def _report_major_updates(self, major_updates: list[MajorUpdate]) -> None:
        self.console.print(
            "\n[bold yellow]📦 Major Version Updates Available[/ bold yellow]",
        )
        self.console.print(
            "[yellow]The following packages have major updates: [/ yellow]\n",
        )

        for update in major_updates:
            self.console.print(f"[yellow]• {update.package}[/ yellow]")
            self.console.print(f" [dim]Current: {update.current_version}[/ dim]")
            self.console.print(f" [dim]Latest: {update.latest_version}[/ dim]")
            if update.release_date:
                release_date = update.release_date[:10]
                self.console.print(f" [dim]Released: {release_date}[/ dim]")
            if update.breaking_changes:
                self.console.print(" [red]⚠️ May contain breaking changes[/ red]")
            self.console.print()

        self.console.print(
            "[dim]Review changelogs before updating to major versions.[/ dim]",
        )

    def force_check_updates(
        self,
    ) -> tuple[list[DependencyVulnerability], list[MajorUpdate]]:
        if not self.pyproject_path.exists():
            self.console.print("[yellow]⚠️ No pyproject.toml found[/ yellow]")
            return [], []

        self.console.print("[dim]Parsing dependencies from pyproject.toml...[/ dim]")
        dependencies = self._parse_dependencies()
        if not dependencies:
            self.console.print(
                "[yellow]⚠️ No dependencies found in pyproject.toml[/ yellow]",
            )
            return [], []

        self.console.print(
            f"[dim]Found {len(dependencies)} dependencies to check[/ dim]",
        )

        self.console.print("[dim]Checking for security vulnerabilities...[/ dim]")
        vulnerabilities = self._check_security_vulnerabilities(dependencies)

        self.console.print("[dim]Checking for major version updates...[/ dim]")
        major_updates = self._check_major_updates(dependencies)

        return vulnerabilities, major_updates

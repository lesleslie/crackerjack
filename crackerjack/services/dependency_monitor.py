import json
import subprocess
import tempfile
import time
import tomllib
import typing as t
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from ..models.protocols import FileSystemInterface


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

            dependencies = {}

            if "dependencies" in data.get("project", {}):
                for dep in data["project"]["dependencies"]:
                    name, version = self._parse_dependency_spec(dep)
                    if name and version:
                        dependencies[name] = version

            if "optional-dependencies" in data.get("project", {}):
                for group_deps in data["project"]["optional-dependencies"].values():
                    for dep in group_deps:
                        name, version = self._parse_dependency_spec(dep)
                        if name and version:
                            dependencies[name] = version

            return dependencies

        except Exception as e:
            self.console.print(
                f"[yellow]Warning: Failed to parse pyproject.toml: {e}[/yellow]"
            )
            return {}

    def _parse_dependency_spec(self, spec: str) -> tuple[str | None, str | None]:
        if not spec or spec.startswith("-"):
            return None, None

        for operator in (">=", "<=", "==", "~=", "!=", ">", "<"):
            if operator in spec:
                parts = spec.split(operator, 1)
                if len(parts) == 2:
                    package = parts[0].strip()
                    version = parts[1].strip()
                    return package, version

        return spec.strip(), "latest"

    def _check_security_vulnerabilities(
        self, dependencies: dict[str, str]
    ) -> list[DependencyVulnerability]:
        vulnerabilities = []

        safety_vulns = self._check_with_safety(dependencies)
        vulnerabilities.extend(safety_vulns)

        if not vulnerabilities:
            pip_audit_vulns = self._check_with_pip_audit(dependencies)
            vulnerabilities.extend(pip_audit_vulns)

        return vulnerabilities

    def _check_with_safety(
        self, dependencies: dict[str, str]
    ) -> list[DependencyVulnerability]:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                for package, version in dependencies.items():
                    if version != "latest":
                        f.write(f"{package}=={version}\n")
                    else:
                        f.write(f"{package}\n")
                temp_file = f.name

            try:
                result = subprocess.run(
                    ["uv", "run", "safety", "check", "--file", temp_file, "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    return []

                if result.stdout:
                    safety_data = json.loads(result.stdout)
                    return self._parse_safety_output(safety_data)

            finally:
                Path(temp_file).unlink(missing_ok=True)

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            pass
        except Exception:
            pass

        return []

    def _check_with_pip_audit(
        self, dependencies: dict[str, str]
    ) -> list[DependencyVulnerability]:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                for package, version in dependencies.items():
                    if version != "latest":
                        f.write(f"{package}=={version}\n")
                    else:
                        f.write(f"{package}\n")
                temp_file = f.name

            try:
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "pip-audit",
                        "--requirement",
                        temp_file,
                        "--format",
                        "json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    return []

                if result.stdout:
                    audit_data = json.loads(result.stdout)
                    return self._parse_pip_audit_output(audit_data)

            finally:
                Path(temp_file).unlink(missing_ok=True)

        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            pass
        except Exception:
            pass

        return []

    def _parse_safety_output(self, safety_data: t.Any) -> list[DependencyVulnerability]:
        vulnerabilities = []
        from contextlib import suppress

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
                    )
                )

        return vulnerabilities

    def _parse_pip_audit_output(
        self, audit_data: t.Any
    ) -> list[DependencyVulnerability]:
        vulnerabilities = []
        from contextlib import suppress

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
                    )
                )

        return vulnerabilities

    def _check_major_updates(self, dependencies: dict[str, str]) -> list[MajorUpdate]:
        major_updates = []
        cache = self._load_update_cache()
        current_time = time.time()

        for package, current_version in dependencies.items():
            if current_version == "latest":
                continue

            cache_key = f"{package}_{current_version}"
            if cache_key in cache:
                cached_data = cache[cache_key]
                if current_time - cached_data["timestamp"] < 86400:
                    if cached_data["has_major_update"]:
                        major_updates.append(
                            MajorUpdate(
                                package=package,
                                current_version=current_version,
                                latest_version=cached_data["latest_version"],
                                release_date=cached_data["release_date"],
                                breaking_changes=cached_data["breaking_changes"],
                            )
                        )
                    continue

            latest_info = self._get_latest_version_info(package)
            if latest_info:
                has_major_update = self._is_major_version_update(
                    current_version, latest_info["version"]
                )

                cache[cache_key] = {
                    "timestamp": current_time,
                    "has_major_update": has_major_update,
                    "latest_version": latest_info["version"],
                    "release_date": latest_info["release_date"],
                    "breaking_changes": latest_info["breaking_changes"],
                }

                if has_major_update:
                    major_updates.append(
                        MajorUpdate(
                            package=package,
                            current_version=current_version,
                            latest_version=latest_info["version"],
                            release_date=latest_info["release_date"],
                            breaking_changes=latest_info["breaking_changes"],
                        )
                    )

        self._save_update_cache(cache)
        return major_updates

    def _get_latest_version_info(self, package: str) -> dict[str, t.Any] | None:
        try:
            import urllib.error
            import urllib.request

            url = f"https://pypi.org/pypi/{package}/json"

            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.load(response)

            info = data.get("info", {})
            releases = data.get("releases", {})

            latest_version = info.get("version", "")
            if not latest_version:
                return None

            release_info = releases.get(latest_version, [])
            release_date = ""
            if release_info:
                release_date = release_info[0].get("upload_time", "")

            breaking_changes = (
                latest_version.split(".")[0] != "0" if "." in latest_version else False
            )

            return {
                "version": latest_version,
                "release_date": release_date,
                "breaking_changes": breaking_changes,
            }

        except Exception:
            return None

    def _is_major_version_update(self, current: str, latest: str) -> bool:
        from contextlib import suppress

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
        from contextlib import suppress

        with suppress(Exception):
            if self.cache_file.exists():
                with self.cache_file.open() as f:
                    return json.load(f)
        return {}

    def _save_update_cache(self, cache: dict[str, t.Any]) -> None:
        from contextlib import suppress

        with suppress(Exception):
            self.cache_file.parent.mkdir(exist_ok=True)
            with self.cache_file.open("w") as f:
                json.dump(cache, f, indent=2)

    def _report_vulnerabilities(
        self, vulnerabilities: list[DependencyVulnerability]
    ) -> None:
        self.console.print(
            "\n[bold red]🚨 Security Vulnerabilities Found![/bold red]"
        )
        self.console.print(
            "[red]Please update the following packages immediately:[/red]\n"
        )

        for vuln in vulnerabilities:
            self.console.print(
                f"[red]• {vuln.package} {vuln.installed_version}[/red]"
            )
            self.console.print(
                f" [dim]Vulnerability ID: {vuln.vulnerability_id}[/dim]"
            )
            self.console.print(f" [dim]Severity: {vuln.severity.upper()}[/dim]")
            if vuln.patched_version:
                self.console.print(
                    f" [green]Fix available: {vuln.patched_version}[/green]"
                )
            if vuln.advisory_url:
                self.console.print(f" [dim]More info: {vuln.advisory_url}[/dim]")
            self.console.print()

    def _report_major_updates(self, major_updates: list[MajorUpdate]) -> None:
        self.console.print(
            "\n[bold yellow]📦 Major Version Updates Available[/bold yellow]"
        )
        self.console.print(
            "[yellow]The following packages have major updates:[/yellow]\n"
        )

        for update in major_updates:
            self.console.print(f"[yellow]• {update.package}[/yellow]")
            self.console.print(f" [dim]Current: {update.current_version}[/dim]")
            self.console.print(f" [dim]Latest: {update.latest_version}[/dim]")
            if update.release_date:
                release_date = update.release_date[:10]
                self.console.print(f" [dim]Released: {release_date}[/dim]")
            if update.breaking_changes:
                self.console.print(" [red]⚠️ May contain breaking changes[/red]")
            self.console.print()

        self.console.print(
            "[dim]Review changelogs before updating to major versions.[/dim]"
        )

    def force_check_updates(
        self,
    ) -> tuple[list[DependencyVulnerability], list[MajorUpdate]]:
        if not self.pyproject_path.exists():
            self.console.print("[yellow]⚠️ No pyproject.toml found[/yellow]")
            return [], []

        self.console.print("[dim]Parsing dependencies from pyproject.toml...[/dim]")
        dependencies = self._parse_dependencies()
        if not dependencies:
            self.console.print(
                "[yellow]⚠️ No dependencies found in pyproject.toml[/yellow]"
            )
            return [], []

        self.console.print(
            f"[dim]Found {len(dependencies)} dependencies to check[/dim]"
        )

        self.console.print("[dim]Checking for security vulnerabilities...[/dim]")
        vulnerabilities = self._check_security_vulnerabilities(dependencies)

        self.console.print("[dim]Checking for major version updates...[/dim]")
        major_updates = self._check_major_updates(dependencies)

        return vulnerabilities, major_updates

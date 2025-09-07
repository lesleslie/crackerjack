import subprocess
import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console

from crackerjack.models.protocols import FileSystemInterface, SecurityServiceProtocol


class PublishManagerImpl:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        dry_run: bool = False,
        filesystem: FileSystemInterface | None = None,
        security: SecurityServiceProtocol | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.dry_run = dry_run

        if filesystem is None:
            from crackerjack.services.filesystem import FileSystemService

            filesystem = FileSystemService()

        if security is None:
            from crackerjack.services.security import SecurityService

            security = SecurityService()

        self.filesystem = filesystem
        self.security = security

    def _run_command(
        self,
        cmd: list[str],
        timeout: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        secure_env = self.security.create_secure_command_env()

        result = subprocess.run(
            cmd,
            check=False,
            cwd=self.pkg_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=secure_env,
        )

        if result.stdout:
            result.stdout = self.security.mask_tokens(result.stdout)
        if result.stderr:
            result.stderr = self.security.mask_tokens(result.stderr)

        return result

    def _get_current_version(self) -> str | None:
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return None
        try:
            from tomllib import loads

            content = self.filesystem.read_file(pyproject_path)
            data = loads(content)
            return data.get("project", {}).get("version")
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Error reading version: {e}")
            return None

    def _update_version_in_file(self, new_version: str) -> bool:
        pyproject_path = self.pkg_path / "pyproject.toml"
        try:
            content = self.filesystem.read_file(pyproject_path)
            from crackerjack.services.regex_patterns import update_pyproject_version

            new_content = update_pyproject_version(content, new_version)
            if content != new_content:
                if not self.dry_run:
                    self.filesystem.write_file(pyproject_path, new_content)
                self.console.print(
                    f"[green]✅[/ green] Updated version to {new_version}",
                )
                return True
            self.console.print(
                "[yellow]⚠️[/ yellow] Version pattern not found in pyproject.toml",
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error updating version: {e}")
            return False

    def _calculate_next_version(self, current: str, bump_type: str) -> str:
        try:
            parts = current.split(".")
            if len(parts) != 3:
                msg = f"Invalid version format: {current}"
                raise ValueError(msg)
            major, minor, patch = map(int, parts)
            if bump_type == "major":
                return f"{major + 1}.0.0"
            if bump_type == "minor":
                return f"{major}.{minor + 1}.0"
            if bump_type == "patch":
                return f"{major}.{minor}.{patch + 1}"
            msg = f"Invalid bump type: {bump_type}"
            raise ValueError(msg)
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Error calculating version: {e}")
            raise

    def bump_version(self, version_type: str) -> str:
        current_version = self._get_current_version()
        if not current_version:
            self.console.print("[red]❌[/ red] Could not determine current version")
            msg = "Cannot determine current version"
            raise ValueError(msg)
        self.console.print(f"[cyan]📦[/ cyan] Current version: {current_version}")

        if version_type == "interactive":
            version_type = self._prompt_for_version_type()

        try:
            new_version = self._calculate_next_version(current_version, version_type)
            if self.dry_run:
                self.console.print(
                    f"[yellow]🔍[/ yellow] Would bump {version_type} version: {current_version} → {new_version}",
                )
            elif self._update_version_in_file(new_version):
                self.console.print(
                    f"[green]🚀[/ green] Bumped {version_type} version: {current_version} → {new_version}",
                )
            else:
                msg = "Failed to update version in file"
                raise ValueError(msg)

            return new_version
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Version bump failed: {e}")
            raise

    def _prompt_for_version_type(self) -> str:
        try:
            from rich.prompt import Prompt

            return Prompt.ask(
                "[cyan]📦[/ cyan] Select version bump type",
                choices=["patch", "minor", "major"],
                default="patch",
            )
        except ImportError:
            self.console.print(
                "[yellow]⚠️[/ yellow] Rich prompt not available, defaulting to patch"
            )
            return "patch"

    def validate_auth(self) -> bool:
        auth_methods = self._collect_auth_methods()
        return self._report_auth_status(auth_methods)

    def _collect_auth_methods(self) -> list[str]:
        auth_methods: list[str] = []

        env_auth = self._check_env_token_auth()
        if env_auth:
            auth_methods.append(env_auth)

        keyring_auth = self._check_keyring_auth()
        if keyring_auth:
            auth_methods.append(keyring_auth)

        return auth_methods

    def _check_env_token_auth(self) -> str | None:
        import os

        token = os.getenv("UV_PUBLISH_TOKEN")
        if not token:
            return None

        if self.security.validate_token_format(token, "pypi"):
            masked_token = self.security.mask_tokens(token)
            self.console.print(f"[dim]Token format: {masked_token}[/ dim]", style="dim")
            return "Environment variable (UV_PUBLISH_TOKEN)"
        self.console.print(
            "[yellow]⚠️[/ yellow] UV_PUBLISH_TOKEN format appears invalid",
        )
        return None

    def _check_keyring_auth(self) -> str | None:
        try:
            result = self._run_command(
                [
                    "keyring",
                    "get",
                    "https://upload.pypi.org/legacy/",
                    "__token__",
                ],
            )
            if result.returncode == 0 and result.stdout.strip():
                keyring_token = result.stdout.strip()
                if self.security.validate_token_format(keyring_token, "pypi"):
                    return "Keyring storage"
                self.console.print(
                    "[yellow]⚠️[/ yellow] Keyring token format appears invalid",
                )
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        return None

    def _report_auth_status(self, auth_methods: list[str]) -> bool:
        if auth_methods:
            self.console.print("[green]✅[/ green] PyPI authentication available: ")
            for method in auth_methods:
                self.console.print(f"-{method}")
            return True
        self._display_auth_setup_instructions()
        return False

    def _display_auth_setup_instructions(self) -> None:
        self.console.print("[red]❌[/ red] No valid PyPI authentication found")
        self.console.print("\n[yellow]💡[/ yellow] Setup options: ")
        self.console.print(
            " 1. Set environment variable: export UV_PUBLISH_TOKEN=<your-pypi-token>",
        )
        self.console.print(
            " 2. Use keyring: keyring set https://upload.pypi.org/legacy/ __token__",
        )
        self.console.print(
            " 3. Ensure token starts with 'pypi-' and is properly formatted",
        )

    def build_package(self) -> bool:
        try:
            self.console.print("[yellow]🔨[/ yellow] Building package...")

            if self.dry_run:
                return self._handle_dry_run_build()

            return self._execute_build()
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Build error: {e}")
            return False

    def _handle_dry_run_build(self) -> bool:
        self.console.print("[yellow]🔍[/ yellow] Would build package")
        return True

    def _clean_dist_directory(self) -> None:
        dist_dir = self.pkg_path / "dist"
        if not dist_dir.exists():
            return

        try:
            import shutil

            shutil.rmtree(dist_dir)
            dist_dir.mkdir(exist_ok=True)
            self.console.print(
                "[cyan]🧹[/ cyan] Cleaned dist directory for fresh build"
            )
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Warning: Could not clean dist directory: {e}"
            )

    def _execute_build(self) -> bool:
        self._clean_dist_directory()

        result = self._run_command(["uv", "build"])

        if result.returncode != 0:
            self.console.print(f"[red]❌[/ red] Build failed: {result.stderr}")
            return False

        self.console.print("[green]✅[/ green] Package built successfully")
        self._display_build_artifacts()
        return True

    def _display_build_artifacts(self) -> None:
        dist_dir = self.pkg_path / "dist"
        if not dist_dir.exists():
            return

        artifacts = list(dist_dir.glob("*"))
        self.console.print(f"[cyan]📦[/ cyan] Build artifacts ({len(artifacts)}): ")

        for artifact in artifacts[-5:]:
            size_str = self._format_file_size(artifact.stat().st_size)
            self.console.print(f"-{artifact.name} ({size_str})")

    def _format_file_size(self, size: int) -> str:
        if size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        return f"{size / (1024 * 1024):.1f}MB"

    def publish_package(self) -> bool:
        if not self._validate_prerequisites():
            return False

        try:
            self.console.print("[yellow]🚀[/ yellow] Publishing to PyPI...")
            return self._perform_publish_workflow()
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Publish error: {e}")
            return False

    def _validate_prerequisites(self) -> bool:
        return self.validate_auth()

    def _perform_publish_workflow(self) -> bool:
        if self.dry_run:
            return self._handle_dry_run_publish()

        if not self.build_package():
            return False

        return self._execute_publish()

    def _handle_dry_run_publish(self) -> bool:
        self.console.print("[yellow]🔍[/ yellow] Would publish package to PyPI")
        return True

    def _execute_publish(self) -> bool:
        result = self._run_command(["uv", "publish"])

        if result.returncode != 0:
            self._handle_publish_failure(result.stderr)
            return False

        self._handle_publish_success()
        return True

    def _handle_publish_failure(self, error_msg: str) -> None:
        self.console.print(f"[red]❌[/ red] Publish failed: {error_msg}")

    def _handle_publish_success(self) -> None:
        self.console.print("[green]🎉[/ green] Package published successfully !")
        self._display_package_url()

    def _display_package_url(self) -> None:
        current_version = self._get_current_version()
        package_name = self._get_package_name()

        if package_name and current_version:
            url = f"https://pypi.org/project/{package_name}/{current_version}/"
            self.console.print(f"[cyan]🔗[/ cyan] Package URL: {url}")

    def _get_package_name(self) -> str | None:
        pyproject_path = self.pkg_path / "pyproject.toml"

        with suppress(Exception):
            from tomllib import loads

            content = self.filesystem.read_file(pyproject_path)
            data = loads(content)
            return data.get("project", {}).get("name", "")

        return None

    def cleanup_old_releases(self, keep_releases: int = 10) -> bool:
        try:
            self.console.print(
                f"[yellow]🧹[/ yellow] Cleaning up old releases (keeping {keep_releases})...",
            )
            if self.dry_run:
                self.console.print(
                    "[yellow]🔍[/ yellow] Would clean up old PyPI releases",
                )
                return True
            pyproject_path = self.pkg_path / "pyproject.toml"
            from tomllib import loads

            content = self.filesystem.read_file(pyproject_path)
            data = loads(content)
            package_name = data.get("project", {}).get("name", "")
            if not package_name:
                self.console.print(
                    "[yellow]⚠️[/ yellow] Could not determine package name",
                )
                return False
            self.console.print(
                f"[cyan]📦[/ cyan] Would analyze releases for {package_name}",
            )
            self.console.print(
                f"[cyan]🔧[/ cyan] Would keep {keep_releases} most recent releases",
            )

            return True
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Cleanup error: {e}")
            return False

    def create_git_tag(self, version: str) -> bool:
        try:
            if self.dry_run:
                self.console.print(
                    f"[yellow]🔍[/ yellow] Would create git tag: v{version}",
                )
                return True
            result = self._run_command(["git", "tag", f"v{version}"])
            if result.returncode == 0:
                self.console.print(f"[green]🏷️[/ green] Created git tag: v{version}")
                push_result = self._run_command(
                    ["git", "push", "origin", f"v{version}"],
                )
                if push_result.returncode == 0:
                    self.console.print("[green]📤[/ green] Pushed tag to remote")
                else:
                    self.console.print(
                        f"[yellow]⚠️[/ yellow] Tag created but push failed: {push_result.stderr}",
                    )

                return True
            self.console.print(
                f"[red]❌[/ red] Failed to create tag: {result.stderr}",
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Tag creation error: {e}")
            return False

    def get_package_info(self) -> dict[str, t.Any]:
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return {}
        try:
            from tomllib import loads

            content = self.filesystem.read_file(pyproject_path)
            data = loads(content)
            project = data.get("project", {})

            return {
                "name": project.get("name", ""),
                "version": project.get("version", ""),
                "description": project.get("description", ""),
                "authors": project.get("authors", []),
                "dependencies": project.get("dependencies", []),
                "python_requires": project.get("requires-python", ""),
            }
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Error reading package info: {e}")
            return {}

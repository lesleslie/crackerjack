import subprocess
import typing as t
from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.protocols import (
    ChangelogGeneratorProtocol,
    FileSystemInterface,
    GitServiceProtocol,
    RegexPatternsProtocol,
    SecurityServiceProtocol,
    VersionAnalyzerProtocol,
)
from crackerjack.utils.retry_utils import retry_api_call


class PublishManagerImpl:
    @depends.inject  # type: ignore[misc]
    def __init__(
        self,
        git_service: Inject[GitServiceProtocol],
        version_analyzer: Inject[VersionAnalyzerProtocol],
        changelog_generator: Inject[ChangelogGeneratorProtocol],
        filesystem: Inject[FileSystemInterface],
        security: Inject[SecurityServiceProtocol],
        regex_patterns: Inject[RegexPatternsProtocol],
        console: Inject[Console],
        pkg_path: Inject[Path],
        dry_run: bool = False,
    ) -> None:
        # Foundation dependencies
        self.console = console
        self.pkg_path = pkg_path
        self.dry_run = dry_run

        # Services injected via ACB DI
        self._git_service = git_service
        self._version_analyzer = version_analyzer
        self._changelog_generator = changelog_generator
        self._regex_patterns = regex_patterns
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
            version = data.get("project", {}).get("version")
            return version if isinstance(version, str) else None
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Error reading version: {e}")
            return None

    def _update_version_in_file(self, new_version: str) -> bool:
        pyproject_path = self.pkg_path / "pyproject.toml"
        try:
            content = self.filesystem.read_file(pyproject_path)

            # Use injected service or get through ACB DI
            if self._regex_patterns is not None:
                update_pyproject_version_func = (
                    self._regex_patterns.update_pyproject_version
                )
            else:
                from acb.depends import depends

                update_pyproject_version_func = depends.get_sync(
                    RegexPatternsProtocol
                ).update_pyproject_version

            new_content = update_pyproject_version_func(content, new_version)
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

        # Get intelligent version analysis and recommendation
        recommendation = self._get_version_recommendation()
        if recommendation and version_type != "interactive":
            self._display_version_analysis(recommendation)
            if version_type == "auto":
                version_type = recommendation.bump_type.value
                self.console.print(
                    f"[green]🎯[/green] Using AI-recommended bump type: {version_type}"
                )

        if version_type == "interactive":
            version_type = self._prompt_for_version_type(recommendation)

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
                # Update changelog after successful version bump
                self._update_changelog_for_version(current_version, new_version)
            else:
                msg = "Failed to update version in file"
                raise ValueError(msg)

            return new_version
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Version bump failed: {e}")
            raise

    def _prompt_for_version_type(self, recommendation: t.Any = None) -> str:
        try:
            from rich.prompt import Prompt

            default_type = "patch"
            if recommendation:
                default_type = recommendation.bump_type.value
                self.console.print(
                    f"[dim]AI recommendation: {default_type} (confidence: {recommendation.confidence:.0%})[/dim]"
                )

            return Prompt.ask(
                "[cyan]📦[/ cyan] Select version bump type",
                choices=["patch", "minor", "major"],
                default=default_type,
            )
        except ImportError:
            self.console.print(
                "[yellow]⚠️[/ yellow] Rich prompt not available, defaulting to patch"
            )
            return "patch"

    def _get_version_recommendation(self) -> t.Any:
        """Get AI-powered version bump recommendation based on git history."""
        try:
            import asyncio

            # Use injected version analyzer service
            version_analyzer = self._version_analyzer

            # Get recommendation asynchronously
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a new event loop in a thread if one is already running
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, version_analyzer.recommend_version_bump()
                        )
                        recommendation = future.result(timeout=10)
                else:
                    recommendation = loop.run_until_complete(
                        version_analyzer.recommend_version_bump()
                    )
            except RuntimeError:
                # No event loop, create one
                recommendation = asyncio.run(version_analyzer.recommend_version_bump())

            return recommendation

        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Version analysis failed: {e}")
            return None

    def _display_version_analysis(self, recommendation: t.Any) -> None:
        """Display version analysis in a compact format."""
        if not recommendation:
            return

        self.console.print("\n[cyan]🎯 AI Version Analysis[/cyan]")
        self.console.print(
            f"Recommended: [bold green]{recommendation.recommended_version}[/bold green] "
            f"({recommendation.bump_type.value.upper()}) - {recommendation.confidence:.0%} confidence"
        )

        if recommendation.reasoning:
            self.console.print(f"[dim]→ {recommendation.reasoning[0]}[/dim]")

        # Show key changes briefly
        if recommendation.breaking_changes:
            self.console.print(
                f"[red]⚠️[/red] {len(recommendation.breaking_changes)} breaking changes detected"
            )
        elif recommendation.new_features:
            self.console.print(
                f"[green]✨[/green] {len(recommendation.new_features)} new features detected"
            )
        elif recommendation.bug_fixes:
            self.console.print(
                f"[blue]🔧[/blue] {len(recommendation.bug_fixes)} bug fixes detected"
            )

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
            " 2. Use keyring: keyring set[t.Any] https://upload.pypi.org/legacy/ __token__",
        )
        self.console.print(
            " 3. Ensure token starts with 'pypi-' and is properly formatted",
        )

    def build_package(self) -> bool:
        try:
            self.console.print("[yellow]🔨[/ yellow] Building package")

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

        artifacts = list[t.Any](dist_dir.glob("*"))
        self.console.print(f"[cyan]📦[/ cyan] Build artifacts ({len(artifacts)}): ")

        for artifact in artifacts[-5:]:
            size_str = self._format_file_size(artifact.stat().st_size)
            self.console.print(f"-{artifact.name} ({size_str})")

    def _format_file_size(self, size: int) -> str:
        if size < 1024 * 1024:
            return f"{size / 1024: .1f}KB"
        return f"{size / (1024 * 1024): .1f}MB"

    def publish_package(self) -> bool:
        if not self._validate_prerequisites():
            return False

        try:
            self.console.print("[yellow]🚀[/ yellow] Publishing to PyPI")
            return self._perform_publish_workflow_with_retry()
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

    @retry_api_call(max_attempts=3, delay=2.0, backoff=2.0, max_delay=60.0)
    def _perform_publish_workflow_with_retry(self) -> bool:
        """Perform the publish workflow with retry logic for API connection errors."""
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

        # Check for success indicators in output even if return code is non-zero
        # UV can return non-zero codes for warnings while still succeeding
        success_indicators = [
            "Successfully uploaded",
            "Package uploaded successfully",
            "Upload successful",
            "Successfully published",
        ]

        has_success_indicator = (
            any(indicator in result.stdout for indicator in success_indicators)
            if result.stdout
            else False
        )

        # Consider it successful if either return code is 0 OR we find success indicators
        success = result.returncode == 0 or has_success_indicator

        if success:
            self._handle_publish_success()
            return True

        self._handle_publish_failure(result.stderr)
        return False

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
            name = data.get("project", {}).get("name", "")
            return name if isinstance(name, str) else None

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

    def create_git_tag_local(self, version: str) -> bool:
        """Create git tag locally without pushing (for use with push_with_tags)."""
        try:
            if self.dry_run:
                self.console.print(
                    f"[yellow]🔍[/ yellow] Would create git tag: v{version}",
                )
                return True
            result = self._run_command(["git", "tag", f"v{version}"])
            if result.returncode == 0:
                self.console.print(f"[green]🏷️[/ green] Created git tag: v{version}")
                return True
            self.console.print(
                f"[red]❌[/ red] Failed to create tag: {result.stderr}",
            )
            return False
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Tag creation error: {e}")
            return False

    def create_git_tag(self, version: str) -> bool:
        """Create git tag and push it immediately (legacy method for standalone use)."""
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

    def _update_changelog_for_version(self, old_version: str, new_version: str) -> None:
        """Update changelog with entries from git commits since last version."""
        try:
            # Use injected changelog generator service
            changelog_generator = self._changelog_generator

            # Look for changelog file
            changelog_path = self.pkg_path / "CHANGELOG.md"

            # Generate changelog entries since last version
            success = changelog_generator.generate_changelog_from_commits(
                changelog_path=changelog_path,
                version=new_version,
                since_version=f"v{old_version}",  # Assumes git tags are prefixed with 'v'
            )

            if success:
                self.console.print(
                    f"[green]📝[/green] Updated changelog for version {new_version}"
                )
            else:
                self.console.print(
                    "[yellow]⚠️[/yellow] Changelog update encountered issues"
                )

        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Failed to update changelog: {e}")

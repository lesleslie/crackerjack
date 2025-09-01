"""Configuration integrity checking service.

This module handles detection of configuration file changes and validates
required configuration sections. Split from tool_version_service.py.
"""

from pathlib import Path

from rich.console import Console


class ConfigIntegrityService:
    """Service for checking configuration file integrity and required sections."""

    def __init__(self, console: Console, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def check_config_integrity(self) -> bool:
        """Check for configuration file drift and missing required sections."""
        config_files = [
            ".pre-commit-config.yaml",
            "pyproject.toml",
        ]

        drift_detected = False

        for file_name in config_files:
            file_path = self.project_path / file_name
            if file_path.exists() and self._check_file_drift(file_path):
                drift_detected = True

        if not self._has_required_config_sections():
            self.console.print(
                "[yellow]⚠️ Configuration missing required sections[/yellow]",
            )
            drift_detected = True

        return drift_detected

    def _check_file_drift(self, file_path: Path) -> bool:
        """Check if a configuration file has been modified since last check."""
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
                            f"[yellow]⚠️ {file_path.name} has been modified manually[/yellow]",
                        )
                        return True

            cache_file.write_text(str(current_hash))
            return False

        except OSError as e:
            self.console.print(f"[red]❌ Error checking {file_path.name}: {e}[/red]")
            return False

    def _has_required_config_sections(self) -> bool:
        """Check if pyproject.toml has all required configuration sections."""
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
                            f"[yellow]⚠️ Missing required config section: {section}[/yellow]",
                        )
                        return False
                    current = current[key]

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error parsing pyproject.toml: {e}[/red]")
            return False

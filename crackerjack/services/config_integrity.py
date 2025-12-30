import tomllib
import typing as t
from pathlib import Path

from crackerjack.exceptions.config import ConfigIntegrityError
from crackerjack.models.protocols import ConfigIntegrityServiceProtocol, ServiceProtocol


class ConfigIntegrityService(ConfigIntegrityServiceProtocol, ServiceProtocol):
    def __init__(self, project_path: Path) -> None:
        self.console = console
        self.project_path = project_path
        self.cache_dir = Path.home() / ".cache" / "crackerjack"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def check_config_integrity(self) -> bool:
        config_files = [
            "pyproject.toml",
        ]

        drift_detected = False

        for file_name in config_files:
            file_path = self.project_path / file_name
            if file_path.exists():
                try:
                    if self._check_file_drift(file_path):
                        drift_detected = True
                except ConfigIntegrityError as e:
                    self.console.print(
                        f"[red]❌ Error checking {file_path.name}: {e}[/ red]"
                    )
                    drift_detected = True

        try:
            if not self._has_required_config_sections():
                drift_detected = True
        except ConfigIntegrityError as e:
            self.console.print(f"[red]❌ Configuration integrity error: {e}[/ red]")
            drift_detected = True

        return drift_detected

    def _check_file_drift(self, file_path: Path) -> bool:
        cache_file = self.cache_dir / f"{file_path.name}.hash"

        try:
            current_content = file_path.read_text()
            current_hash = hash(current_content)

            if cache_file.exists():
                cached_hash = int(cache_file.read_text().strip())
                if current_hash != cached_hash:
                    self.console.print(
                        f"[yellow]⚠️ {file_path.name} has been modified manually[/ yellow]",
                    )
                    return True

            cache_file.write_text(str(current_hash))
            return False

        except OSError as e:
            raise ConfigIntegrityError(
                f"Failed to check file drift for {file_path.name}: {e}"
            ) from e

    def _has_required_config_sections(self) -> bool:
        pyproject = self.project_path / "pyproject.toml"
        if not pyproject.exists():
            raise ConfigIntegrityError("pyproject.toml not found.")

        try:
            with pyproject.open("rb") as f:
                config = tomllib.load(f)
        except Exception as e:
            raise ConfigIntegrityError(f"Error parsing pyproject.toml: {e}") from e

        required = ["tool.ruff", "tool.pyright", "tool.pytest.ini_options"]

        for section in required:
            keys = section.split(".")
            current = config

            for key in keys:
                if key not in current:
                    raise ConfigIntegrityError(
                        f"Missing required config section: {section} in pyproject.toml"
                    )
                current = current[key]

        return True

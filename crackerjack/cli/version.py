from pathlib import Path


def get_package_version() -> str:
    try:
        from importlib.metadata import version

        return version("crackerjack")
    except (ImportError, ModuleNotFoundError):
        try:
            import tomllib

            pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
            with pyproject_path.open("rb") as f:
                pyproject_data = tomllib.load(f)
            version_value = pyproject_data["project"]["version"]
            return str(version_value)
        except Exception:
            return "unknown"

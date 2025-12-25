import asyncio
from pathlib import Path

import pytest

from crackerjack.documentation.mkdocs_integration import (
    MkDocsIntegrationService,
    MkDocsSiteBuilder,
)


class DummyConfigManager:
    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def save(self) -> bool:
        return True

    def load(self) -> bool:
        return True


class DummyFileSystem:
    def read_file(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str | Path, content: str) -> None:
        Path(path).write_text(content, encoding="utf-8")

    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        Path(path).mkdir(parents=parents, exist_ok=True)

    def ensure_directory(self, path: str | Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)


class DummyLogger:
    def info(self, message: str, **kwargs: object) -> None:
        return None

    def warning(self, message: str, **kwargs: object) -> None:
        return None

    def error(self, message: str, **kwargs: object) -> None:
        return None

    def debug(self, message: str, **kwargs: object) -> None:
        return None


def _build_service() -> MkDocsIntegrationService:
    return MkDocsIntegrationService(
        config_manager=DummyConfigManager(),
        filesystem=DummyFileSystem(),
        logger=DummyLogger(),
    )


def test_generate_site_basic(tmp_path: Path) -> None:
    """Test basic functionality of generate_site."""
    service = _build_service()
    config = service.create_config_from_project(
        project_name="Test Project",
        project_description="Test description",
        author="Tester",
    )
    docs_content = {"index.md": "# Hello"}

    site = asyncio.run(
        service.generate_site(
            docs_content=docs_content,
            config=config,
            output_dir=tmp_path,
        )
    )

    assert site.build_path is not None
    assert (site.build_path / "mkdocs.yml").exists()
    assert (site.build_path / "docs" / "index.md").exists()

def test_build_site_basic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test basic functionality of build_site."""
    service = _build_service()
    config = service.create_config_from_project(
        project_name="Test Project",
        project_description="Test description",
        author="Tester",
    )
    docs_content = {"index.md": "# Hello"}

    site = asyncio.run(
        service.generate_site(
            docs_content=docs_content,
            config=config,
            output_dir=tmp_path,
        )
    )

    class DummyResult:
        returncode = 0
        stderr = ""

    def fake_run(*args: object, **kwargs: object) -> DummyResult:
        return DummyResult()

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert asyncio.run(service.build_site(site)) is True

def test_create_config_from_project_basic() -> None:
    """Test basic functionality of create_config_from_project."""
    service = _build_service()
    config = service.create_config_from_project(
        project_name="Test Project",
        project_description="Test description",
        author="Tester",
        repo_url="https://example.com/repo",
    )

    assert config.site_name == "Test Project"
    assert config.site_description == "Test description"
    assert config.site_author == "Tester"
    assert config.repo_url == "https://example.com/repo"

def test_build_documentation_site_basic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test basic functionality of build_documentation_site."""
    service = _build_service()
    builder = MkDocsSiteBuilder(service)
    docs_content = {"index.md": "# Hello"}

    async def fake_build_site(*args: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(service, "build_site", fake_build_site)

    site = asyncio.run(
        builder.build_documentation_site(
            project_name="Test Project",
            project_description="Test description",
            author="Tester",
            documentation_content=docs_content,
            output_dir=tmp_path,
        )
    )

    assert site is not None

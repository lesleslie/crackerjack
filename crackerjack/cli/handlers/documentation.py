import typing as t
from pathlib import Path

from rich.console import Console

console = Console()


def generate_documentation(doc_service: t.Any) -> bool:
    console.print("📖 [bold blue]Generating API documentation...[/bold blue]")
    success = doc_service.generate_full_api_documentation()
    if success:
        console.print(
            "✅ [bold green]Documentation generated successfully![/bold green]"
        )
        return True
    console.print("❌ [bold red]Documentation generation failed![/bold red]")
    return False


def validate_documentation_files(doc_service: t.Any) -> None:
    console.print("🔍 [bold blue]Validating documentation...[/bold blue]")
    doc_paths = [Path("docs"), Path("README.md"), Path("CHANGELOG.md")]
    existing_docs = [p for p in doc_paths if p.exists()]

    if existing_docs:
        issues = doc_service.validate_documentation(existing_docs)
        if issues:
            console.print(f"⚠️ Found {len(issues)} documentation issues:")
            for issue in issues:
                file_path = issue.get("path", issue.get("file", "unknown"))
                console.print(f" - {file_path}: {issue['message']}")
        else:
            console.print(
                "✅ [bold green]Documentation validation passed![/bold green]"
            )
    else:
        console.print("⚠️ No documentation files found to validate")


def handle_documentation_commands(
    generate_docs: bool, validate_docs: bool, options: t.Any
) -> bool:
    if not (generate_docs or validate_docs):
        return True

    from crackerjack.services.documentation_service import DocumentationServiceImpl

    pkg_path = Path.cwd()
    doc_service = DocumentationServiceImpl(pkg_path=pkg_path)

    if generate_docs:
        if not generate_documentation(doc_service):
            return False

    if validate_docs:
        validate_documentation_files(doc_service)

    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def create_sync_filesystem_service() -> t.Any:
    class SyncFileSystemService:
        def read_file(self, path: str | Path) -> str:
            return Path(path).read_text()

        def write_file(self, path: str | Path, content: str) -> None:
            Path(path).write_text(content)

        def exists(self, path: str | Path) -> bool:
            return Path(path).exists()

        def mkdir(self, path: str | Path, parents: bool = False) -> None:
            Path(path).mkdir(parents=parents, exist_ok=True)

        def ensure_directory(self, path: str | Path) -> None:
            Path(path).mkdir(parents=True, exist_ok=True)

    return SyncFileSystemService()


def create_config_manager() -> t.Any:
    class ConfigManager:
        def __init__(self) -> None:
            self._config: dict[str, t.Any] = {}

        def get(self, key: str, default: t.Any = None) -> t.Any:
            return self._config.get(key, default)

        def set(self, key: str, value: t.Any) -> None:
            self._config[key] = value

        def save(self) -> bool:
            return True

        def load(self) -> bool:
            return True

    return ConfigManager()


def create_logger_adapter(logger: t.Any) -> t.Any:
    class LoggerAdapter:
        def __init__(self, logger: t.Any) -> None:
            self._logger = logger

        def debug(self, message: str, **kwargs: t.Any) -> None:
            self._logger.debug(message)

        def info(self, message: str, **kwargs: t.Any) -> None:
            self._logger.info(message)

        def warning(self, message: str, **kwargs: t.Any) -> None:
            self._logger.warning(message)

        def error(self, message: str, **kwargs: t.Any) -> None:
            self._logger.error(message)

    return LoggerAdapter(logger)


def create_mkdocs_services() -> dict[str, t.Any]:
    from logging import getLogger

    from crackerjack.documentation.mkdocs_integration import (
        MkDocsIntegrationService,
        MkDocsSiteBuilder,
    )

    filesystem = create_sync_filesystem_service()
    config_manager = create_config_manager()
    logger = getLogger(__name__)
    logger_adapter = create_logger_adapter(logger)

    integration_service = MkDocsIntegrationService(
        config_manager, filesystem, logger_adapter
    )
    builder = MkDocsSiteBuilder(integration_service)

    return {"builder": builder, "filesystem": filesystem, "config": config_manager}


def determine_mkdocs_output_dir(mkdocs_output: str | None) -> Path:
    return Path(mkdocs_output) if mkdocs_output else Path.cwd() / "docs_site"


def create_sample_docs_content() -> dict[str, str]:
    return {
        "index.md": "# Project Documentation\n\nWelcome to the project documentation.",
        "getting-started.md": "# Getting Started\n\nQuick start guide for the project.",
        "api-reference.md": "# API Reference\n\nAPI documentation and examples.",
    }


def build_mkdocs_site(
    builder: t.Any, docs_content: dict[str, str], output_dir: Path, serve: bool
) -> None:
    import asyncio

    asyncio.run(
        builder.build_documentation_site(
            project_name="Project Documentation",
            project_description="Comprehensive project documentation",
            author="Crackerjack",
            documentation_content=docs_content,
            output_dir=output_dir,
            serve=serve,
        )
    )


def handle_mkdocs_build_result(site: t.Any, mkdocs_serve: bool) -> None:
    if site:
        console.print(
            f"[green]✅[/green] MkDocs site generated successfully at: {site.build_path}"
        )
        console.print(
            f"[blue]📄[/blue] Generated {len(site.pages)} documentation pages"
        )

        if mkdocs_serve:
            console.print(
                "[blue]🌐[/blue] MkDocs development server started at http://127.0.0.1:8000"
            )
            console.print("[yellow]Press Ctrl+C to stop the server[/yellow]")
    else:
        console.print("[red]❌[/red] Failed to generate MkDocs site")


def handle_mkdocs_integration(
    mkdocs_integration: bool,
    mkdocs_serve: bool,
    mkdocs_theme: str,
    mkdocs_output: str | None,
) -> bool:
    if not mkdocs_integration:
        return True

    console.print("[cyan]📚[/cyan] Generating MkDocs documentation site...")

    try:
        services = create_mkdocs_services()
        builder = services["builder"]
        output_dir = determine_mkdocs_output_dir(mkdocs_output)
        docs_content = create_sample_docs_content()

        console.print(
            f"[blue]🏗️[/blue] Building documentation site with {mkdocs_theme} theme..."
        )

        build_mkdocs_site(builder, docs_content, output_dir, mkdocs_serve)
        site = None
        handle_mkdocs_build_result(site, mkdocs_serve)

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] MkDocs integration error: {e}")
        return False

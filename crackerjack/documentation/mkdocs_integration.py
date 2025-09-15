"""MkDocs integration system for crackerjack documentation generation.

This module provides seamless integration with MkDocs for generating comprehensive
documentation websites with automatic configuration and content management.
"""

import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from ..models.protocols import (
    ConfigManagerProtocol,
    FileSystemServiceProtocol,
    LoggerProtocol,
)


@dataclass
class MkDocsConfig:
    """Configuration for MkDocs site generation."""

    site_name: str
    site_description: str
    site_author: str
    site_url: str | None = None
    repo_url: str | None = None
    theme: str = "material"
    nav_structure: dict[str, str] | None = None
    plugins: list[str] | None = None
    extra_css: list[str] | None = None
    extra_javascript: list[str] | None = None
    markdown_extensions: list[str] | None = None


@dataclass
class DocumentationSite:
    """Represents a complete documentation site."""

    config: MkDocsConfig
    pages: dict[str, str]
    assets: dict[str, bytes]
    generated_at: datetime
    build_path: Path | None = None


class MkDocsIntegrationService:
    """Service for integrating with MkDocs documentation generation."""

    def __init__(
        self,
        config_manager: ConfigManagerProtocol,
        filesystem: FileSystemServiceProtocol,
        logger: LoggerProtocol,
    ):
        self.config_manager = config_manager
        self.filesystem = filesystem
        self.logger = logger
        self._default_theme_config = self._get_default_theme_config()

    async def generate_site(
        self,
        docs_content: dict[str, str],
        config: MkDocsConfig,
        output_dir: Path,
    ) -> DocumentationSite:
        """Generate a complete MkDocs site from documentation content.

        Args:
            docs_content: Dictionary mapping file paths to content
            config: MkDocs configuration settings
            output_dir: Directory to generate site in

        Returns:
            Generated documentation site information
        """
        self.logger.info(f"Generating MkDocs site: {config.site_name}")

        # Create site structure
        site_dir = output_dir / "site"
        docs_dir = site_dir / "docs"

        self.filesystem.ensure_directory(site_dir)
        self.filesystem.ensure_directory(docs_dir)

        # Generate mkdocs.yml
        mkdocs_config = self._create_mkdocs_config(config, docs_content)
        config_path = site_dir / "mkdocs.yml"
        self.filesystem.write_file(
            config_path,
            yaml.dump(mkdocs_config, default_flow_style=False, sort_keys=False),
        )

        # Write documentation files
        pages = {}
        for file_path, content in docs_content.items():
            doc_path = docs_dir / file_path
            self.filesystem.ensure_directory(doc_path.parent)
            self.filesystem.write_file(doc_path, content)
            pages[file_path] = content

        # Copy theme assets if needed
        assets = await self._copy_theme_assets(site_dir, config.theme)

        site = DocumentationSite(
            config=config,
            pages=pages,
            assets=assets,
            generated_at=datetime.now(),
            build_path=site_dir,
        )

        self.logger.info(f"Generated MkDocs site at: {site_dir}")
        return site

    async def build_site(self, site: DocumentationSite, serve: bool = False) -> bool:
        """Build the MkDocs site to static HTML.

        Args:
            site: Documentation site to build
            serve: Whether to start development server

        Returns:
            True if build successful, False otherwise
        """
        if not site.build_path:
            self.logger.error("Site has no build path set[t.Any]")
            return False

        try:
            # Build command
            build_cmd = ["mkdocs", "build"]
            if serve:
                build_cmd = ["mkdocs", "serve", "--dev-addr", "127.0.0.1:8000"]

            # Run in site directory
            import subprocess

            result = subprocess.run(
                build_cmd,
                cwd=site.build_path,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.logger.error(f"MkDocs build failed: {result.stderr}")
                return False

            if serve:
                self.logger.info(
                    "MkDocs development server started at http://127.0.0.1:8000"
                )
            else:
                self.logger.info("MkDocs site built successfully")

            return True

        except Exception as e:
            self.logger.error(f"Failed to build MkDocs site: {e}")
            return False

    def create_config_from_project(
        self,
        project_name: str,
        project_description: str,
        author: str,
        repo_url: str | None = None,
    ) -> MkDocsConfig:
        """Create MkDocs configuration from project metadata.

        Args:
            project_name: Name of the project
            project_description: Description of the project
            author: Project author
            repo_url: Repository URL if available

        Returns:
            Configured MkDocsConfig instance
        """
        return MkDocsConfig(
            site_name=project_name,
            site_description=project_description,
            site_author=author,
            repo_url=repo_url,
            theme="material",
            nav_structure=self._get_default_nav_structure(),
            plugins=self._get_default_plugins(),
            markdown_extensions=self._get_default_extensions(),
        )

    def _create_mkdocs_config(
        self,
        config: MkDocsConfig,
        docs_content: dict[str, str],
    ) -> dict[str, t.Any]:
        """Create mkdocs.yml configuration dictionary.

        Args:
            config: MkDocs configuration
            docs_content: Documentation content for nav generation

        Returns:
            Configuration dictionary for mkdocs.yml
        """
        mkdocs_config: dict[str, t.Any] = {
            "site_name": config.site_name,
            "site_description": config.site_description,
            "site_author": config.site_author,
        }

        if config.site_url:
            mkdocs_config["site_url"] = config.site_url

        if config.repo_url:
            mkdocs_config["repo_url"] = config.repo_url
            mkdocs_config["repo_name"] = self._extract_repo_name(config.repo_url)

        # Theme configuration
        if config.theme == "material":
            mkdocs_config["theme"] = {
                "name": "material",
                "features": [
                    "navigation.sections",
                    "navigation.expand",
                    "navigation.top",
                    "search.highlight",
                    "search.share",
                ],
                "palette": [
                    {
                        "scheme": "default",
                        "primary": "blue",
                        "accent": "blue",
                        "toggle": {
                            "icon": "material/brightness-7",
                            "name": "Switch to dark mode",
                        },
                    },
                    {
                        "scheme": "slate",
                        "primary": "blue",
                        "accent": "blue",
                        "toggle": {
                            "icon": "material/brightness-4",
                            "name": "Switch to light mode",
                        },
                    },
                ],
            }
        else:
            mkdocs_config["theme"] = {"name": config.theme}

        # Navigation
        nav = config.nav_structure or self._generate_nav_from_content(docs_content)
        if nav:
            mkdocs_config["nav"] = nav

        # Plugins
        plugins = config.plugins or self._get_default_plugins()
        if plugins:
            mkdocs_config["plugins"] = plugins

        # Markdown extensions
        extensions = config.markdown_extensions or self._get_default_extensions()
        if extensions:
            mkdocs_config["markdown_extensions"] = extensions

        # Extra CSS/JS
        if config.extra_css:
            mkdocs_config["extra_css"] = config.extra_css

        if config.extra_javascript:
            mkdocs_config["extra_javascript"] = config.extra_javascript

        return mkdocs_config

    def _get_default_theme_config(self) -> dict[str, t.Any]:
        """Get default theme configuration."""
        return {
            "material": {
                "features": [
                    "navigation.sections",
                    "navigation.expand",
                    "navigation.top",
                    "search.highlight",
                    "search.share",
                ],
                "palette": {
                    "scheme": "default",
                    "primary": "blue",
                    "accent": "blue",
                },
            }
        }

    def _get_default_nav_structure(self) -> dict[str, str]:
        """Get default navigation structure."""
        return {
            "Home": "index.md",
            "Getting Started": "getting-started.md",
            "User Guide": "user-guide.md",
            "API Reference": "api-reference.md",
            "Development": "development.md",
        }

    def _get_default_plugins(self) -> list[str]:
        """Get default MkDocs plugins."""
        return [
            "search",
            "autorefs",
            "mkdocstrings",
        ]

    def _get_default_extensions(self) -> list[str]:
        """Get default Markdown extensions."""
        return [
            "markdown.extensions.toc",
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
            "markdown.extensions.admonition",
            "pymdownx.details",
            "pymdownx.superfences",
            "pymdownx.highlight",
            "pymdownx.inlinehilite",
            "pymdownx.snippets",
        ]

    def _generate_nav_from_content(
        self, docs_content: dict[str, str]
    ) -> list[dict[str, str]]:
        """Generate navigation structure from documentation content.

        Args:
            docs_content: Dictionary of file paths to content

        Returns:
            Navigation structure list[t.Any]
        """
        nav = []

        # Sort files by logical order
        sorted_files = sorted(docs_content.keys())

        # Special handling for common files
        priority_files = ["index.md", "README.md", "getting-started.md"]
        regular_files = [f for f in sorted_files if f not in priority_files]

        for priority_file in priority_files:
            if priority_file in docs_content:
                title = self._file_to_title(priority_file)
                nav.append({title: priority_file})

        for file_path in regular_files:
            title = self._file_to_title(file_path)
            nav.append({title: file_path})

        return nav

    def _file_to_title(self, file_path: str) -> str:
        """Convert file path to navigation title.

        Args:
            file_path: File path to convert

        Returns:
            Human-readable title
        """
        # Remove extension and directory path
        name = Path(file_path).stem

        # Convert various formats to title case
        if name in ("index", "README"):
            return "Home"

        # Convert snake_case and kebab-case to Title Case
        title = name.replace("_", " ").replace("-", " ")
        title = " ".join(word.capitalize() for word in title.split())

        return title

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL.

        Args:
            repo_url: Repository URL

        Returns:
            Repository name
        """
        repo_url = repo_url.removesuffix(".git")

        return repo_url.split("/")[-1]

    async def _copy_theme_assets(
        self,
        site_dir: Path,
        theme: str,
    ) -> dict[str, bytes]:
        """Copy theme-specific assets to site directory.

        Args:
            site_dir: Site directory path
            theme: Theme name

        Returns:
            Dictionary of copied assets
        """
        assets = {}

        # For material theme, we might want to copy custom CSS
        if theme == "material":
            custom_css_content = self._get_material_custom_css()
            if custom_css_content:
                css_dir = site_dir / "docs" / "stylesheets"
                self.filesystem.ensure_directory(css_dir)
                css_path = css_dir / "extra.css"
                self.filesystem.write_file(css_path, custom_css_content)
                assets["stylesheets/extra.css"] = custom_css_content.encode()

        return assets

    def _get_material_custom_css(self) -> str:
        """Get custom CSS for Material theme.

        Returns:
            Custom CSS content
        """
        return """
/* Custom CSS for Crackerjack documentation */
.md-header {
    background-color: var(--md-primary-fg-color--dark);
}

.md-nav__title {
    font-weight: 700;
}

/* Code block improvements */
.md-typeset .codehilite,
.md-typeset .highlight {
    margin: 1em 0;
}

/* Admonition styling */
.md-typeset .admonition {
    border-radius: 0.2rem;
    margin: 1.5625em 0;
}

/* Table improvements */
.md-typeset table:not([class]) {
    font-size: 0.8rem;
}
"""


class MkDocsSiteBuilder:
    """High-level builder for MkDocs documentation sites."""

    def __init__(self, integration_service: MkDocsIntegrationService) -> None:
        self.integration = integration_service

    async def build_documentation_site(
        self,
        project_name: str,
        project_description: str,
        author: str,
        documentation_content: dict[str, str],
        output_dir: Path,
        repo_url: str | None = None,
        serve: bool = False,
    ) -> DocumentationSite | None:
        """Build a complete documentation site.

        Args:
            project_name: Name of the project
            project_description: Project description
            author: Project author
            documentation_content: Documentation content by file path
            output_dir: Output directory for site
            repo_url: Repository URL if available
            serve: Whether to start development server

        Returns:
            Built documentation site or None if failed
        """
        try:
            # Create configuration
            config = self.integration.create_config_from_project(
                project_name=project_name,
                project_description=project_description,
                author=author,
                repo_url=repo_url,
            )

            # Generate site
            site = await self.integration.generate_site(
                docs_content=documentation_content,
                config=config,
                output_dir=output_dir,
            )

            # Build site
            success = await self.integration.build_site(site, serve=serve)

            if success:
                return site
            else:
                return None

        except Exception as e:
            self.integration.logger.error(f"Failed to build documentation site: {e}")
            return None

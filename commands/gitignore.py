#!/usr/bin/env python3
"""
Gitignore Management Command for Crackerjack

Provides comprehensive .gitignore file management across all repositories.
Ensures consistent ignore patterns, validates templates, and manages project-specific rules.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import click
from pydantic import BaseModel, Field, validator

from crackerjack import Config
from crackerjack.integration.mahavishnu_integration import (
    MahavishnuAggregator,
    MahavishnuConfig,
    RepositoryVelocity,
)


logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class GitignoreCheck(BaseModel):
    """Result of checking a repository's .gitignore file."""

    repository_path: str = Field(description="Absolute or relative path to repository")
    has_gitignore: bool = Field(description="Whether .gitignore exists")
    gitignore_size: int = Field(description="Size of .gitignore in bytes")
    is_template: bool = Field(default=False, description="Whether using standard template")
    pattern_count: int = Field(description="Number of unique patterns")
    missing_patterns: list[str] = Field(default_factory=list, description="Missing recommended patterns")


class StandardizeRequest(BaseModel):
    """Request to standardize a repository's .gitignore file."""

    repository_path: str = Field(description="Path to repository")
    backup: bool = Field(default=False, description="Backup existing .gitignore before changes")
    force: bool = Field(default=False, description="Force overwrite even if exists")


class ApplyTemplateRequest(BaseModel):
    """Request to apply template to a repository."""

    repository_path: str = Field(description="Path to repository")
    template_path: Optional[str] = Field(default=None, description="Custom template path (uses default if not specified)")


class BatchOperation(BaseModel):
    """Request for batch operations on multiple repositories."""

    operation: str = Field(description="Operation: check, standardize, apply-template")
    paths: list[str] = Field(description="List of repository paths")
    options: dict = Field(default_factory=dict, description="Additional options per operation")


# ============================================================================
# Constants
# ============================================================================

GITIGNORE_TEMPLATE = Path(".claude/projects/GITIGNORE_TEMPLATE.md")

STANDARD_PATTERNS = {
    "python_cache": ["__pycache__/", "*.py[cod]", "*$py.class", "*.so"],
    "python_compiled": ["*.pyc", "*.pyo"],
    "build_artifacts": ["build/", "dist/", "develop-eggs/", "eggs/", "lib/", "lib64/", "parts/", "sdist/"],
    "packaging": ["*.egg-info", "installed.cfg", "*.egg", "MANIFEST", "*.spec", "*.whl"],
    "test_coverage": ["htmlcov/", "tox/", ".nox/", "coverage.*", "*.cover", "*.py,cover", ".hypothesis/", ".pytest_cache/"],
    "package_managers": [".pdm-python/", ".pdm.toml", ".pyscn/", ".uv/", ".uv-cache/"],
    "type_checking": [".mypy_cache/", ".dmypy.json", "dmypy.json", ".ruff_cache/", ".pyre/", ".pytype/", ".pytype/"],
    "python_env": [".env", ".venv", "venv/", "env/", "venv/", "ENV/"],
    "transient": [".idea/", ".vscode/", "*.swp", "*.swo", "*~"],
    "logs": ["*.log", "logs/"],
    "os": [".DS_Store", "Thumbs.db"],
    "config": ["settings/local.yaml", "settings/repos.yaml", "settings/ecosystem.yaml", ".envrc.local"],
    "sensitive": ["config.yaml", "oneiric.yaml"],
    "crackerjack": [".crackerjack/"],
    "archived": [".archive/", "tests/archived/"],
}

RECOMMENDED_PATTERNS = set(STANDARD_PATTERNS["python_cache"] + STANDARD_PATTERNS["build_artifacts"])


# ============================================================================
# Helper Functions
# ============================================================================

def load_template() -> str:
    """Load the .gitignore template file."""
    if not GITIGNORE_TEMPLATE.exists():
        logger.warning(f"Template not found at {GITIGNORE_TEMPLATE}")
        return ""

    with open(GITIGNORE_TEMPLATE, "r") as f:
        return f.read()


def check_gitignore(repo_path: Path) -> GitignoreCheck:
    """Check if repository has a .gitignore file and analyze it."""
    gitignore_path = repo_path / ".gitignore"

    if not gitignore_path.exists():
        return GitignoreCheck(
            repository_path=str(repo_path),
            has_gitignore=False,
            gitignore_size=0,
            is_template=False,
            pattern_count=0,
            missing_patterns=list(STANDARD_PATTERNS.values()),
        )

    with open(gitignore_path, "r") as f:
        content = f.read()
        lines = [line.strip() for line in content if line.strip() and not line.startswith("#")]

    # Check for template usage
    is_template = "Template Version:" in content

    # Count unique patterns
    patterns = set()
    for line in lines:
        # Extract pattern (handle both .gitignore and common patterns)
        if line.startswith("#"):
            continue
        pattern = line.strip()
        # Remove common wildcards for comparison
        pattern_base = re.sub(r"[*!?.\[\]{}\^]", "", pattern)
        patterns.add(pattern_base)

    return GitignoreCheck(
        repository_path=str(repo_path),
        has_gitignore=True,
        gitignore_size=len(content),
        is_template=is_template,
        pattern_count=len(patterns),
        missing_patterns=[],
    )


def validate_patterns(repo_path: Path) -> list[str]:
    """Validate .gitignore patterns and return missing recommended ones."""
    gitignore_path = repo_path / ".gitignore"

    if not gitignore_path.exists():
        return list(STANDARD_PATTERNS.values())

    with open(gitignore_path, "r") as f:
        content = f.read()

    existing_patterns = set()
    for line in content:
        line = line.strip()
        if line.startswith("#") or not line:
            continue

        pattern = line.strip()
        pattern_base = re.sub(r"[*!?.\[\]{}\^]", "", pattern)
        existing_patterns.add(pattern_base)

    # Find missing patterns
    missing = []
    for category, patterns in STANDARD_PATTERNS.items():
        if category == "crackerjack":
            continue  # Skip project-specific
        for pattern in patterns:
            if pattern not in existing_patterns:
                missing.append(pattern)

    return missing


# ============================================================================
# Click Commands
# ============================================================================

@click.group()
@click.pass_context
def main(config: Config) -> None:
    """Gitignore management command."""

    # Gitignore Check Command
    @click.group()
    def check(paths: list[str], recursive: bool = False) -> list[GitignoreCheck]:
        """Check repositories for .gitignore presence and patterns."""
        results = []

        for path_str in paths:
            repo_path = Path(path_str).expanduser().resolve()

            if not repo_path.exists():
                logger.warning(f"Repository not found: {repo_path}")
                continue

            result = check_gitignore(repo_path)
            results.append(result)

        if not results:
            logger.info("No repositories checked")

        return results

    @check.command()
    def standardize(
        paths: list[str],
        backup: bool = False,
        force: bool = False,
        template_path: Optional[str] = None,
    ) -> list[GitignoreCheck]:
        """Standardize .gitignore files across repositories."""
        template = load_template() if not template_path else ""

        if not template:
            logger.warning("No template available - using minimal defaults")

        results = []
        for path_str in paths:
            repo_path = Path(path_str).expanduser().resolve()

            if not repo_path.exists():
                logger.warning(f"Repository not found: {repo_path}")
                continue

            # Backup existing if requested
            gitignore_path = repo_path / ".gitignore"
            if backup and gitignore_path.exists():
                backup_path = repo_path / ".gitignore.backup"

                with open(gitignore_path, "r") as existing:
                    existing_content = existing_content.read()

                with open(gitignore_path, "w") as backup:
                    backup.write(existing_content)

                logger.info(f"Backed up {gitignore_path} to {backup_path}")

            # Apply template
            with open(gitignore_path, "w") as f:
                f.write(template)

            result = GitignoreCheck(
                repository_path=str(repo_path),
                has_gitignore=True,
                gitignore_size=len(template),
                is_template=True,
                pattern_count=len(template.split("\n")),
                missing_patterns=[],
            )
            results.append(result)

            logger.info(f"Standardized {repo_path}")

        return results

    @check.command()
    def validate(paths: list[str], recursive: bool = False) -> list[GitignoreCheck]:
        """Validate .gitignore patterns against recommended standards."""
        results = []

        for path_str in paths:
            repo_path = Path(path_str).expanduser().resolve()

            if not repo_path.exists():
                logger.warning(f"Repository not found: {repo_path}")
                continue

            missing = validate_patterns(repo_path)

            result = GitignoreCheck(
                repository_path=str(repo_path),
                has_gitignore=True,
                gitignore_size=0,  # Not checking size
                is_template=False,
                pattern_count=0,
                missing_patterns=missing,
            )
            results.append(result)

            if missing:
                logger.warning(f"{repo_path} missing {len(missing)} recommended patterns")
            else:
                logger.info(f"{repo_path} .gitignore is valid")

        return results

    @click.command()
    def batch(
        operation: str,
        paths: list[str],
        **kwargs,
    ) -> dict:
        """Execute batch operations on multiple repositories."""
        results = {}

        if operation == "check":
            results_list = check(paths, recursive=kwargs.get("recursive", False))
            return {
                "operation": operation,
                "results": [r.dict() for r in results_list],
            }

        elif operation == "validate":
            results_list = validate(paths, recursive=kwargs.get("recursive", False))
            return {
                "operation": operation,
                "results": [r.dict() for r in results_list],
            }

        elif operation == "standardize":
            results_list = standardize(
                paths,
                backup=kwargs.get("backup", False),
                force=kwargs.get("force", False),
                template_path=kwargs.get("template_path"),
            )
            return {
                "operation": operation,
                "results": [r.dict() for r in results_list],
            }

        else:
            logger.error(f"Unknown operation: {operation}")
            return {"operation": operation, "error": f"Unknown operation"}

    # Main command group
    @click.group()
    def gitignore(
        paths: list[str] = Field(
            description="Repository paths to process",
            example=["/Users/les/Projects/mahavishnu", "/Users/les/Projects/crackerjack"],
        ),
        operation: click.Choice(
            "check",
            "validate",
            "standardize",
            case_sensitive=False,
        ),
        operation_value: str = Field(
            default="check",
            description="Operation to perform",
        ),
        backup: bool = Field(default=False, description="Backup existing .gitignore before standardize"),
        force: bool = Field(default=False, description="Force overwrite even if exists"),
        template_path: str = Field(
            default=None,
            description="Path to custom .gitignore template",
        ),
        recursive: bool = Field(
            default=False,
            description="Search subdirectories recursively",
        ),
    ):
        """Gitignore management command - main entry point."""

        # Connect to Mahavishnu
        try:
            aggregator = MahavishnuAggregator(
                config=MahavishnuConfig(
                    db_path=Path(".crackerjack/mahavishnu.db"),
                    websocket_enabled=False,
                )
            )
            _aggregator = aggregator  # type: ignore
        except Exception as e:
            logger.error(f"Failed to connect to Mahavishnu: {e}")

        ctx = ensure_context(obj={}, _aggregator=_aggregator)

        # Dispatch based on operation
        if paths and operation.operation == "check":
            return _handle_check(ctx, operation, paths)

        elif paths and operation.operation == "validate":
            return _handle_validate(ctx, operation, paths)

        elif paths and operation.operation == "standardize":
            return _handle_standardize(ctx, operation, paths)

        else:
            # Show help
            click.echo(ctx.get())
            gitignore commands([], standalone_mode=True)
            ctx.close()
            return None

    def _handle_check(self, ctx: click.Context, operation: str, paths: list[str]) -> dict:
        """Handle check operation."""
        # Placeholder for implementation
        return {"operation": operation, "results": []}


def _handle_validate(self, ctx: click.Context, operation: str, paths: list[str]) -> dict:
        """Handle validate operation."""
        # Placeholder for implementation
        return {"operation": operation, "results": []}


def _handle_standardize(self, ctx: click.Context, operation: str, paths: list[str]) -> dict:
        """Handle standardize operation."""
        # Placeholder for implementation
        return {"operation": operation, "results": []}


def ensure_context(obj: object, _aggregator) -> MahavishnuAggregator:
    """Ensure Mahavishnu aggregator context is available."""
    if hasattr(obj, "_aggregator") and obj._aggregator is None:
        obj._aggregator = _aggregator
    return obj


if __name__ == "__main__":
    main()

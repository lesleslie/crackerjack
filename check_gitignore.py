#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


GITIGNORE_TEMPLATE = Path(".claude/projects/GITIGNORE_TEMPLATE.md")

STANDARD_PATTERNS = {
    "python_cache": ["__pycache__/", "*.py[cod]", "*$py.class", "*.so"],
    "python_compiled": ["*.pyc", "*.pyo"],
    "build_artifacts": [
        "build/",
        "dist/",
        "develop-eggs/",
        "eggs/",
        "lib/",
        "lib64/",
        "parts/",
        "sdist/",
    ],
    "test_coverage": [
        "htmlcov/",
        "tox/",
        ".nox/",
        "coverage.*",
        "*.cover",
        "*.py,cover",
        ".hypothesis/",
        ".pytest_cache/",
    ],
    "logs": ["*.log", "logs/"],
    "os": [".DS_Store"],
    "config": ["settings/local.yaml", "settings/repos.yaml", ".envrc.local"],
}


def check_repository(repo_path: Path) -> dict:
    gitignore_path = repo_path / ".gitignore"

    if not gitignore_path.exists():
        return {
            "repository": str(repo_path),
            "status": "no_gitignore",
            "has_gitignore": False,
        }

    with open(gitignore_path) as f:
        content = f.read()
        lines = [
            line.strip()
            for line in content
            if line.strip() and not line.startswith("#")
        ]

    patterns = set()
    for line in lines:
        if line.startswith("#") or not line:
            continue

        pattern = line.strip()
        patterns.add(pattern)

    return {
        "repository": str(repo_path),
        "status": "analyzed",
        "has_gitignore": True,
        "size": len(content),
        "pattern_count": len(patterns),
        "patterns": list(patterns),
    }


def standardize_gitignore(repo_path: Path, backup: bool = False) -> dict:
    gitignore_path = repo_path / ".gitignore"

    if not GITIGNORE_TEMPLATE.exists():
        logger.warning(f"Template not found at {GITIGNORE_TEMPLATE}")
        return {
            "repository": str(repo_path),
            "status": "template_not_found",
            "success": False,
        }

    if backup or gitignore_path.exists():
        backup_path = repo_path / ".gitignore.backup"

        with open(gitignore_path) as existing:
            existing_content = existing.read()

        with open(backup_path, "w") as backup:
            backup.write(existing_content)

        logger.info(f"Backed up {gitignore_path} to {backup_path}")

    with open(GITIGNORE_TEMPLATE) as f:
        template = f.read()

    with open(gitignore_path, "w") as f:
        f.write(template)

    return {
        "repository": str(repo_path),
        "status": "standardized",
        "success": True,
        "backup_created": str(backup_path) if backup else "",
    }


def main():

    if len(sys.argv) < 2:
        logger.error("Usage: python check_gitignore.py <repo_path> [repo_path2 ...]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "check":
        repo_path = (
            Path(sys.argv[2])
            if len(sys.argv) > 2
            else Path("/Users/les/Projects/mahavishnu")
        )

        result = check_repository(repo_path)
        print(f"\n=== Gitignore Check: {repo_path} ===")
        print(f"Has .gitignore: {result['has_gitignore']}")
        print(f"Patterns: {result['pattern_count']}")
        if result["pattern_count"] == 0:
            print("WARNING: No patterns found!")
        else:
            print(
                f"Missing recommended patterns: {len(result.get('missing_patterns', []))}"
            )

    elif action == "standardize":
        if len(sys.argv) < 3:
            logger.error(
                "Usage: python check_gitignore.py standardize <repo_path> [--backup]"
            )
            sys.exit(1)

        backup = "--backup" in sys.argv

        repo_path = Path(sys.argv[2])

        result = standardize_gitignore(repo_path, backup=backup)
        print(f"\n=== Standardize: {repo_path} ===")
        print(f"Success: {result['success']}")
        if result.get("backup_created"):
            print(f"Backup: {result['backup_created']}")

    else:
        logger.error(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()

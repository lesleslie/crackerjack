#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path.cwd() / ".session-buddy" / "skills.db"
BACKUP_SUFFIX = ".pre-migration.backup"


def rollback_migration(db_path: Path) -> bool:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Rolling back skills migration...")
    logger.info(f"Database: {db_path}")

    backup_pattern = db_path.stem + BACKUP_SUFFIX
    backup_dir = db_path.parent

    if not backup_dir.exists():
        logger.error(f"Backup directory not found: {backup_dir}")
        return False

    backups = sorted(
        backup_dir.glob(f"{backup_pattern}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        logger.error(f"No backup files found matching: {backup_pattern}*")
        logger.info("If you haven't migrated yet, there's nothing to rollback.")
        return False

    most_recent_backup = backups[0]
    logger.info(f"Found backup: {most_recent_backup}")

    response = input(
        f"⚠️  This will REPLACE {db_path} with {most_recent_backup}. Continue? (yes/no): "
    )

    if response.lower() not in ["yes", "y"]:
        logger.info("Rollback cancelled")
        return False

    if db_path.exists():
        db_path.unlink()
        logger.info(f"Removed current database: {db_path}")

    try:
        shutil.copy2(most_recent_backup, db_path)
        logger.info(f"✅ Rollback complete: restored {most_recent_backup}")
        return True
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rollback skills migration by restoring backup"
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to session-buddy database (default: .session-buddy/skills.db)",
    )

    args = parser.parse_args()

    success = rollback_migration(args.db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


DEFAULT_JSON_PATH = Path.cwd() / ".crackerjack" / "skill_metrics.json"
DEFAULT_DB_PATH = Path.cwd() / ".session-buddy" / "skills.db"
BACKUP_SUFFIX = ".pre-migration.backup"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:

    success: bool
    invocations_migrated: int = 0
    skills_migrated: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    backup_path: Path | None = None

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "Skills Migration Summary",
            "=" * 60,
            "",
            f"Status: {'✅ SUCCESS' if self.success else '❌ FAILED'}",
            f"Duration: {self.duration_seconds:.2f} seconds",
            "",
            f"Invocations migrated: {self.invocations_migrated}",
            f"Skills migrated: {self.skills_migrated}",
            "",
        ]

        if self.warnings:
            lines.extend([
                "Warnings:",
                *[f"  ⚠️  {w}" for w in self.warnings],
                "",
            ])

        if self.errors:
            lines.extend([
                "Errors:",
                *[f"  ❌ {e}" for e in self.errors],
                "",
            ])

        if self.backup_path:
            lines.append(f"Backup: {self.backup_path}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)


@dataclass
class ValidationResult:

    is_valid: bool
    invocations_valid: int = 0
    invocations_invalid: int = 0
    issues: list[str] = field(default_factory=list)


class SkillsMigrator:

    def __init__(
        self,
        json_path: Path,
        db_path: Path,
        dry_run: bool = False,
    ) -> None:
        self.json_path = json_path
        self.db_path = db_path
        self.dry_run = dry_run

    def migrate(self) -> MigrationResult:
        start_time = datetime.now()
        result = MigrationResult(success=False)

        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Starting skills migration...")
        logger.info(f"JSON source: {self.json_path}")
        logger.info(f"Database target: {self.db_path}")


        if not self.json_path.exists():
            result.errors.append(f"JSON file not found: {self.json_path}")
            logger.error(result.errors[-1])
            return result


        if self.db_path.exists():
            result.backup_path = self._backup_database()
            logger.info(f"✅ Database backed up to: {result.backup_path}")


        try:
            json_data = self._load_json()
            logger.info(f"✅ Loaded JSON data")
        except Exception as e:
            result.errors.append(f"Failed to load JSON: {e}")
            logger.error(result.errors[-1])
            return result


        validation = self._validate_json(json_data)
        if not validation.is_valid:
            result.errors.extend(validation.issues)
            logger.error("JSON validation failed:")
            for issue in validation.issues:
                logger.error(f"  - {issue}")
            return result

        logger.info(
            f"✅ JSON validation passed: "
            f"{validation.invocations_valid} valid invocations, "
            f"{validation.invocations_invalid} invalid"
        )

        if validation.invocations_invalid > 0:
            result.warnings.append(
                f"{validation.invocations_invalid} invocations skipped due to validation errors"
            )


        if not self.dry_run:
            try:
                counts = self._migrate_to_dhruva(json_data)
                result.invocations_migrated = counts["invocations"]
                result.skills_migrated = counts["skills"]
                result.success = True

                logger.info(f"✅ Migration complete!")
                logger.info(f"  - Invocations: {result.invocations_migrated}")
                logger.info(f"  - Skills: {result.skills_migrated}")

            except Exception as e:
                result.errors.append(f"Migration failed: {e}")
                logger.exception(result.errors[-1])


                if result.backup_path:
                    logger.info("Attempting rollback due to migration failure...")
                    self._rollback(result.backup_path)
        else:

            counts = self._count_migration_candidates(json_data)
            result.invocations_migrated = counts["invocations"]
            result.skills_migrated = counts["skills"]
            result.success = True

            logger.info(f"🔍 Dry run results (no changes made):")
            logger.info(f"  - Invocations to migrate: {result.invocations_migrated}")
            logger.info(f"  - Skills to migrate: {result.skills_migrated}")


        duration = (datetime.now() - start_time).total_seconds()
        result.duration_seconds = duration

        return result

    def _backup_database(self) -> Path:
        backup_path = self.db_path.with_suffix(BACKUP_SUFFIX)


        counter = 1
        while backup_path.exists():
            backup_path = self.db_path.with_suffix(f"{BACKUP_SUFFIX}.{counter}")
            counter += 1

        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def _load_json(self) -> dict[str, Any]:
        logger.info("Loading JSON metrics...")

        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))


            if not isinstance(data, dict):
                raise ValueError("JSON root must be an object")


            if "invocations" not in data and "skills" not in data:
                raise ValueError(
                    "JSON must contain 'invocations' or 'skills' key"
                )

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e

    def _validate_json(self, data: dict[str, Any]) -> ValidationResult:
        result = ValidationResult(is_valid=True)


        invocations = data.get("invocations", [])
        if not isinstance(invocations, list):
            result.is_valid = False
            result.issues.append("'invocations' must be a list")
            return result

        for idx, inv in enumerate(invocations):
            if not isinstance(inv, dict):
                result.invocations_invalid += 1
                result.issues.append(f"Invocation {idx}: not an object")
                continue


            required_fields = ["skill_name", "invoked_at", "session_id"]
            missing = [f for f in required_fields if f not in inv]

            if missing:
                result.invocations_invalid += 1
                result.issues.append(
                    f"Invocation {idx}: missing fields: {', '.join(missing)}"
                )
            else:
                result.invocations_valid += 1

        return result

    def _count_migration_candidates(self, data: dict[str, Any]) -> dict[str, int]:
        invocations = data.get("invocations", [])
        skills_data = data.get("skills", {})


        unique_skills = set()
        for inv in invocations:
            if isinstance(inv, dict) and "skill_name" in inv:
                unique_skills.add(inv["skill_name"])

        return {
            "invocations": len(invocations),
            "skills": len(unique_skills),
        }

    def _migrate_to_dhruva(self, data: dict[str, Any]) -> dict[str, int]:
        logger.info("Migrating to Dhruva database...")


        try:
            from session_buddy.storage.skills_storage import SkillsStorage
        except ImportError as e:
            raise RuntimeError(
                "session-buddy not available. Install with: pip install session-buddy"
            ) from e


        storage = SkillsStorage(db_path=str(self.db_path))


        invocations = data.get("invocations", [])
        skills_migrated = set()

        invocation_count = 0
        for inv in invocations:
            if not self._is_valid_invocation(inv):
                continue

            try:

                storage.store_invocation(
                    skill_name=inv["skill_name"],
                    invoked_at=inv["invoked_at"],
                    session_id=inv["session_id"],
                    workflow_path=inv.get("workflow_path"),
                    completed=inv.get("completed", False),
                    duration_seconds=inv.get("duration_seconds"),
                    user_query=inv.get("user_query"),
                    alternatives_considered=inv.get("alternatives_considered", []),
                    selection_rank=inv.get("selection_rank"),
                    follow_up_actions=inv.get("follow_up_actions", []),
                    error_type=inv.get("error_type"),
                    workflow_phase=inv.get("workflow_phase"),
                    workflow_step_id=inv.get("workflow_step_id"),
                )

                skills_migrated.add(inv["skill_name"])
                invocation_count += 1

            except Exception as e:
                logger.warning(
                    f"Failed to migrate invocation {inv.get('skill_name')}: {e}"
                )

        return {
            "invocations": invocation_count,
            "skills": len(skills_migrated),
        }

    def _is_valid_invocation(self, inv: dict[str, Any]) -> bool:
        required = ["skill_name", "invoked_at", "session_id"]
        return all(inv.get(field) for field in required)

    def _rollback(self, backup_path: Path) -> bool:
        try:
            if backup_path.exists():

                if self.db_path.exists():
                    self.db_path.unlink()


                shutil.copy2(backup_path, self.db_path)

                logger.info(f"✅ Rollback complete: restored from {backup_path}")
                return True
            else:
                logger.error(f"❌ Rollback failed: backup not found at {backup_path}")
                return False

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return False


def rollback_migration(db_path: Path) -> bool:
    logger.info("Rolling back skills migration...")


    backup_pattern = db_path.stem + BACKUP_SUFFIX
    backup_dir = db_path.parent

    backups = sorted(
        backup_dir.glob(f"{backup_pattern}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        logger.error("No backup files found")
        return False

    most_recent_backup = backups[0]
    logger.info(f"Found backup: {most_recent_backup}")


    if db_path.exists():
        db_path.unlink()
        logger.info(f"Removed current database: {db_path}")


    shutil.copy2(most_recent_backup, db_path)
    logger.info(f"✅ Rollback complete: restored {most_recent_backup}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate crackerjack skills metrics to session-buddy"
    )

    parser.add_argument(
        "--json-path",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="Path to JSON metrics file (default: .crackerjack/skill_metrics.json)",
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to session-buddy database (default: .session-buddy/skills.db)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without making changes",
    )

    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the most recent migration",
    )

    args = parser.parse_args()


    if args.rollback:
        success = rollback_migration(args.db_path)
        sys.exit(0 if success else 1)


    migrator = SkillsMigrator(
        json_path=args.json_path,
        db_path=args.db_path,
        dry_run=args.dry_run,
    )

    result = migrator.migrate()


    print("\n" + result.summary())


    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()

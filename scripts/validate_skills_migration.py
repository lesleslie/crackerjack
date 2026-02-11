#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


DEFAULT_JSON_PATH = Path.cwd() / ".crackerjack" / "skill_metrics.json"
DEFAULT_DB_PATH = Path.cwd() / ".session-buddy" / "skills.db"


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:

    is_valid: bool
    json_invocations: int = 0
    db_invocations: int = 0
    missing_in_db: list[str] = field(default_factory=list)
    extra_in_db: int = 0
    errors: list[str] = field(default_factory=list)


def validate_migration(
    json_path: Path,
    db_path: Path,
) -> ValidationResult:
    result = ValidationResult(is_valid=True)


    if not json_path.exists():
        result.is_valid = False
        result.errors.append(f"JSON file not found: {json_path}")
        return result

    try:
        json_data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Failed to load JSON: {e}")
        return result

    json_invocations = json_data.get("invocations", [])
    result.json_invocations = len(json_invocations)


    if not db_path.exists():
        result.is_valid = False
        result.errors.append(f"Database not found: {db_path}")
        return result

    try:
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()


        cursor.execute("SELECT COUNT(*) FROM skill_invocation")
        result.db_invocations = cursor.fetchone()[0]


        json_skills = set()
        for inv in json_invocations:
            if isinstance(inv, dict) and "skill_name" in inv:
                json_skills.add(inv["skill_name"])


        cursor.execute("SELECT DISTINCT skill_name FROM skill_invocation")
        db_skills = {row[0] for row in cursor.fetchall()}


        result.missing_in_db = sorted(json_skills - db_skills)


        result.extra_in_db = result.db_invocations - len(json_skills & db_skills)

        conn.close()

    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Database query failed: {e}")
        return result


    if result.missing_in_db:
        result.is_valid = False
        result.errors.append(
            f"{len(result.missing_in_db)} skills from JSON not found in database"
        )

    if result.db_invocations != result.json_invocations:
        result.is_valid = False
        result.errors.append(
            f"Invocation count mismatch: JSON={result.json_invocations}, "
            f"DB={result.db_invocations}"
        )

    return result


def print_validation_result(result: ValidationResult) -> None:
    print("\n" + "=" * 60)
    print("Skills Migration Validation")
    print("=" * 60)
    print("")

    status = "✅ VALID" if result.is_valid else "❌ INVALID"
    print(f"Status: {status}")
    print("")

    print(f"JSON invocations: {result.json_invocations}")
    print(f"Database invocations: {result.db_invocations}")
    print("")

    if result.missing_in_db:
        print(f"⚠️  Skills in JSON but not in database ({len(result.missing_in_db)}):")
        for skill in result.missing_in_db[:10]:
            print(f"  - {skill}")
        if len(result.missing_in_db) > 10:
            print(f"  ... and {len(result.missing_in_db) - 10} more")
        print("")

    if result.extra_in_db > 0:
        print(f"ℹ️  Extra invocations in database: {result.extra_in_db}")
        print("")

    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  ❌ {error}")
        print("")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate skills migration integrity"
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

    args = parser.parse_args()

    result = validate_migration(args.json_path, args.db_path)
    print_validation_result(result)

    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()

"""Test data management and cleanup utilities.

Provides utilities for:
- Managing test data lifecycle
- Database cleanup and reset
- Temporary file management
- Test environment isolation
"""

import asyncio
import json
import logging
import shutil
import sqlite3
import tempfile
from collections.abc import Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from session_mgmt_mcp.reflection_tools import ReflectionDatabase
from tests.fixtures.data_factories import (
    LargeDatasetFactory,
    ProjectDataFactory,
    ReflectionDataFactory,
    SessionDataFactory,
)

logger = logging.getLogger(__name__)


class TestDataManager:
    """Manages test data lifecycle and cleanup."""

    def __init__(self, base_temp_dir: Path | None = None) -> None:
        self.base_temp_dir = base_temp_dir or Path(tempfile.gettempdir())
        self.temp_dirs: list[Path] = []
        self.temp_files: list[Path] = []
        self.databases: list[ReflectionDatabase] = []
        self.cleanup_callbacks: list[callable] = []

    @contextmanager
    def temp_directory(self, prefix: str = "session_mgmt_test_") -> Generator[Path]:
        """Create and manage temporary directory."""
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_temp_dir))
        self.temp_dirs.append(temp_dir)

        try:
            yield temp_dir
        finally:
            self._cleanup_directory(temp_dir)

    @contextmanager
    def temp_file(self, suffix: str = ".tmp", prefix: str = "test_") -> Generator[Path]:
        """Create and manage temporary file."""
        temp_file = Path(
            tempfile.mktemp(suffix=suffix, prefix=prefix, dir=self.base_temp_dir),
        )
        self.temp_files.append(temp_file)

        try:
            yield temp_file
        finally:
            self._cleanup_file(temp_file)

    @asynccontextmanager
    async def temp_database(self, populate: bool = False) -> ReflectionDatabase:
        """Create and manage temporary test database."""
        with self.temp_file(suffix=".db", prefix="test_reflections_") as db_path:
            db = ReflectionDatabase(str(db_path))
            self.databases.append(db)

            try:
                await db._ensure_tables()

                if populate:
                    await self._populate_test_database(db)

                yield db
            finally:
                if db.conn:
                    db.conn.close()

    async def _populate_test_database(self, db: ReflectionDatabase) -> None:
        """Populate database with test data."""
        # Add variety of test reflections
        test_reflections = ReflectionDataFactory.build_batch(50)

        for reflection in test_reflections:
            await db.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection.get("tags", []),
            )

    def create_test_project_structure(self, base_path: Path, project_name: str) -> Path:
        """Create realistic test project structure."""
        project_path = base_path / project_name
        project_path.mkdir(parents=True, exist_ok=True)

        # Standard project files
        files = {
            "README.md": f"# {project_name}\n\nTest project for session management MCP testing.",
            "pyproject.toml": f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Test project for session management"
dependencies = [
    "fastapi>=0.100.0",
    "pydantic>=2.0.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
            ".gitignore": """__pycache__/
*.py[cod]
*$py.class
*.so
.coverage
htmlcov/
.tox/
.cache
.pytest_cache/
.env
.venv
env/
venv/
""",
            "src/__init__.py": "",
            "src/main.py": '''"""Main application module."""

def main():
    print("Hello from test project!")

if __name__ == "__main__":
    main()
''',
            "tests/__init__.py": "",
            "tests/test_main.py": '''"""Test main module."""
import pytest
from src.main import main

def test_main():
    """Test main function."""
    main()  # Should not raise
''',
            "requirements.txt": """fastapi>=0.100.0
pydantic>=2.0.0
pytest>=7.0.0
""",
            ".env.example": """# Example environment variables
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=your-secret-key-here
DEBUG=True
""",
        }

        for file_path, content in files.items():
            full_path = project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        return project_path

    def create_git_repository(self, project_path: Path):
        """Initialize git repository in project."""
        git_dir = project_path / ".git"
        git_dir.mkdir(exist_ok=True)

        # Create minimal git structure
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (git_dir / "config").write_text("""[core]
	repositoryformatversion = 0
	filemode = true
	bare = false
	logallrefupdates = true
""")

        # Create refs structure
        refs_dir = git_dir / "refs"
        refs_dir.mkdir(exist_ok=True)
        (refs_dir / "heads").mkdir(exist_ok=True)
        (refs_dir / "tags").mkdir(exist_ok=True)

        # Create empty objects and refs
        objects_dir = git_dir / "objects"
        objects_dir.mkdir(exist_ok=True)
        (objects_dir / "info").mkdir(exist_ok=True)
        (objects_dir / "pack").mkdir(exist_ok=True)

    def generate_test_dataset(
        self,
        dataset_type: str,
        size: str = "small",
    ) -> list[dict]:
        """Generate test datasets of various sizes."""
        sizes = {"tiny": 10, "small": 50, "medium": 200, "large": 1000, "xlarge": 5000}

        count = sizes.get(size, 50)

        if dataset_type == "reflections":
            return ReflectionDataFactory.build_batch(count)
        if dataset_type == "sessions":
            return SessionDataFactory.build_batch(count)
        if dataset_type == "projects":
            return ProjectDataFactory.build_batch(count)
        if dataset_type == "large_reflections":
            return LargeDatasetFactory.generate_large_reflection_dataset(count)
        msg = f"Unknown dataset type: {dataset_type}"
        raise ValueError(msg)

    def save_test_data(self, data: Any, file_path: Path):
        """Save test data to file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.suffix == ".json":
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        else:
            # Default to JSON
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

    def load_test_data(self, file_path: Path) -> Any:
        """Load test data from file."""
        if not file_path.exists():
            msg = f"Test data file not found: {file_path}"
            raise FileNotFoundError(msg)

        with open(file_path) as f:
            return json.load(f)

    def register_cleanup_callback(self, callback: callable):
        """Register callback to be called during cleanup."""
        self.cleanup_callbacks.append(callback)

    def _cleanup_directory(self, directory: Path) -> None:
        """Clean up temporary directory."""
        if directory.exists():
            try:
                shutil.rmtree(directory)
            except Exception as e:
                logger.warning(f"Failed to cleanup directory {directory}: {e}")

    def _cleanup_file(self, file_path: Path) -> None:
        """Clean up temporary file."""
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")

    def cleanup_all(self):
        """Clean up all managed resources."""
        # Call cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")

        # Close databases
        for db in self.databases:
            try:
                if db.conn:
                    db.conn.close()
            except Exception as e:
                logger.warning(f"Failed to close database: {e}")

        # Clean up temporary files
        for temp_file in self.temp_files:
            self._cleanup_file(temp_file)

        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            self._cleanup_directory(temp_dir)

        # Clear lists
        self.temp_dirs.clear()
        self.temp_files.clear()
        self.databases.clear()
        self.cleanup_callbacks.clear()


class DatabaseTestHelper:
    """Helper for database testing operations."""

    @staticmethod
    async def reset_database(db: ReflectionDatabase) -> None:
        """Reset database to clean state."""
        try:
            # Drop all tables
            await db._execute_query("DROP TABLE IF EXISTS reflections")
            await db._execute_query("DROP TABLE IF EXISTS conversation_metadata")

            # Recreate tables
            await db._ensure_tables()
        except Exception as e:
            logger.exception(f"Failed to reset database: {e}")
            raise

    @staticmethod
    async def verify_database_integrity(db: ReflectionDatabase) -> dict[str, Any]:
        """Verify database integrity and return health status."""
        integrity_status = {
            "healthy": True,
            "issues": [],
            "table_counts": {},
            "last_checked": datetime.now().isoformat(),
        }

        try:
            # Check table existence
            tables = await db._execute_query(
                "SELECT name FROM sqlite_master WHERE type='table'",
            )
            table_names = [row[0] for row in tables]

            expected_tables = ["reflections", "conversation_metadata"]
            for table in expected_tables:
                if table not in table_names:
                    integrity_status["healthy"] = False
                    integrity_status["issues"].append(f"Missing table: {table}")
                else:
                    # Count rows in each table
                    count_result = await db._execute_query(
                        f"SELECT COUNT(*) FROM {table}",
                    )
                    integrity_status["table_counts"][table] = (
                        count_result[0][0] if count_result else 0
                    )

            # Check for orphaned data or inconsistencies
            # This could be expanded based on specific integrity requirements

        except Exception as e:
            integrity_status["healthy"] = False
            integrity_status["issues"].append(f"Database check failed: {e}")

        return integrity_status

    @staticmethod
    async def backup_database(db: ReflectionDatabase, backup_path: Path) -> None:
        """Create backup of database."""
        try:
            if db.conn:
                # For SQLite, we can use the backup API
                backup_conn = sqlite3.connect(str(backup_path))
                db.conn.backup(backup_conn)
                backup_conn.close()
        except Exception as e:
            logger.exception(f"Failed to backup database: {e}")
            raise

    @staticmethod
    async def restore_database(db: ReflectionDatabase, backup_path: Path) -> None:
        """Restore database from backup."""
        try:
            if not backup_path.exists():
                msg = f"Backup file not found: {backup_path}"
                raise FileNotFoundError(msg)

            # Close current connection
            if db.conn:
                db.conn.close()

            # Copy backup to database location
            shutil.copy2(backup_path, db.db_path)

            # Reconnect
            db.conn = sqlite3.connect(db.db_path)

        except Exception as e:
            logger.exception(f"Failed to restore database: {e}")
            raise


class PerformanceTestDataManager:
    """Specialized manager for performance test data."""

    def __init__(self, data_manager: TestDataManager) -> None:
        self.data_manager = data_manager
        self.performance_data: dict[str, list[float]] = {}
        self.baseline_metrics: dict[str, float] = {}

    def record_performance_metric(self, metric_name: str, value: float):
        """Record performance metric for analysis."""
        if metric_name not in self.performance_data:
            self.performance_data[metric_name] = []
        self.performance_data[metric_name].append(value)

    def set_baseline_metric(self, metric_name: str, value: float):
        """Set baseline value for performance metric."""
        self.baseline_metrics[metric_name] = value

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance test summary."""
        summary = {
            "metrics": {},
            "baselines": self.baseline_metrics,
            "regressions": [],
            "improvements": [],
        }

        for metric_name, values in self.performance_data.items():
            if not values:
                continue

            import statistics

            metric_stats = {
                "count": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            }

            summary["metrics"][metric_name] = metric_stats

            # Compare with baseline if available
            if metric_name in self.baseline_metrics:
                baseline = self.baseline_metrics[metric_name]
                current = metric_stats["mean"]
                change_percent = ((current - baseline) / baseline) * 100

                if change_percent > 10:  # 10% regression threshold
                    summary["regressions"].append(
                        {
                            "metric": metric_name,
                            "baseline": baseline,
                            "current": current,
                            "change_percent": change_percent,
                        },
                    )
                elif change_percent < -5:  # 5% improvement threshold
                    summary["improvements"].append(
                        {
                            "metric": metric_name,
                            "baseline": baseline,
                            "current": current,
                            "change_percent": change_percent,
                        },
                    )

        return summary

    async def generate_large_dataset_for_testing(
        self,
        db: ReflectionDatabase,
        size: int = 10000,
    ):
        """Generate large dataset for performance testing."""
        batch_size = 100

        for i in range(0, size, batch_size):
            batch_reflections = ReflectionDataFactory.build_batch(
                min(batch_size, size - i),
            )

            # Store batch
            tasks = []
            for reflection in batch_reflections:
                task = db.store_reflection(
                    content=reflection["content"],
                    project=reflection["project"],
                    tags=reflection.get("tags", []),
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Log progress every 1000 records
            if (i + batch_size) % 1000 == 0:
                logger.info(f"Generated {i + batch_size} test records")


# Global test data manager instance
_global_test_data_manager: TestDataManager | None = None


def get_test_data_manager() -> TestDataManager:
    """Get global test data manager instance."""
    global _global_test_data_manager
    if _global_test_data_manager is None:
        _global_test_data_manager = TestDataManager()
    return _global_test_data_manager


def cleanup_test_data():
    """Clean up global test data."""
    global _global_test_data_manager
    if _global_test_data_manager is not None:
        _global_test_data_manager.cleanup_all()
        _global_test_data_manager = None

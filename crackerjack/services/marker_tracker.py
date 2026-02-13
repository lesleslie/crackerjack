"""SQLite-based file hash tracking for incremental scanning.

Features:
- Track MD5 hashes of scanned files per tool
- Detect files needing scan via hash comparison
- Atomic database operations
- Auto-create database directory
"""

import hashlib
import logging
import sqlite3
import typing as t
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MarkerTracker:
    """Track file scan markers in SQLite database."""

    def __init__(self, repo_path: Path) -> None:
        """Initialize tracker.

        Args:
            repo_path: Repository root path
        """
        self.repo_path = Path(repo_path)
        self.db_path = self.repo_path / ".crackerjack" / "scan_markers.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database and create table if needed."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS file_markers (
                        file_path TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        scan_time TEXT NOT NULL,
                        PRIMARY KEY (file_path, tool_name)
                    )
                """)
                conn.commit()

            logger.debug(f"Marker database initialized: {self.db_path}")

        except (sqlite3.Error, OSError) as e:
            logger.error(f"Failed to initialize marker database: {e}")
            raise

    def get_files_needing_scan(
        self,
        tool_name: str,
        all_files: list[Path],
    ) -> list[Path]:
        """Get files that need scanning based on hash comparison.

        Args:
            tool_name: Name of tool
            all_files: All candidate files to check

        Returns:
            Files with changed or missing hashes
        """
        files_needing_scan: list[Path] = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for file_path in all_files:
                    if not file_path.exists():
                        continue

                    try:
                        current_hash = self._calculate_file_hash(file_path)

                        cursor.execute(
                            """
                            SELECT file_hash FROM file_markers
                            WHERE file_path = ? AND tool_name = ?
                            """,
                            (str(file_path), tool_name)
                        )
                        row = cursor.fetchone()

                        if not row or row[0] != current_hash:
                            files_needing_scan.append(file_path)

                    except (OSError, IOError) as e:
                        logger.debug(f"Skipping unreadable file {file_path}: {e}")
                        continue

        except sqlite3.Error as e:
            logger.warning(f"Database error checking files: {e}")
            # Fallback: scan all files
            return [f for f in all_files if f.exists()]

        logger.debug(
            f"{tool_name}: {len(files_needing_scan)} files need scan "
            f"out of {len(all_files)} candidates"
        )

        return files_needing_scan

    def mark_scanned(
        self,
        tool_name: str,
        files: list[Path],
    ) -> None:
        """Mark files as scanned with current hashes.

        Args:
            tool_name: Name of tool
            files: Files that were scanned
        """
        if not files:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                scan_time = datetime.now().isoformat()

                for file_path in files:
                    if not file_path.exists():
                        continue

                    try:
                        file_hash = self._calculate_file_hash(file_path)

                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO file_markers
                            (file_path, tool_name, file_hash, scan_time)
                            VALUES (?, ?, ?, ?)
                            """,
                            (str(file_path), tool_name, file_hash, scan_time)
                        )
                    except (OSError, IOError) as e:
                        logger.debug(f"Skipping unreadable file {file_path}: {e}")
                        continue

                conn.commit()
                logger.debug(f"{tool_name}: Marked {len(files)} files as scanned")

        except sqlite3.Error as e:
            logger.error(f"Failed to mark files as scanned: {e}")

    def mark_full_scan_complete(self, tool_name: str) -> None:
        """Update marker indicating full scan completed.

        Creates/updates a timestamp file to track when the last
        full scan was completed for this tool.

        Args:
            tool_name: Name of tool
        """
        marker_file = self.repo_path / ".crackerjack" / f"{tool_name}_last_full.txt"

        try:
            marker_file.parent.mkdir(parents=True, exist_ok=True)
            marker_file.touch()
            logger.debug(f"Full scan marker updated for {tool_name}")

        except OSError as e:
            logger.warning(f"Failed to create full scan marker: {e}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file contents.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal MD5 hash
        """
        try:
            return hashlib.md5(file_path.read_bytes()).hexdigest()
        except (OSError, IOError) as e:
            logger.warning(f"Failed to hash file {file_path}: {e}")
            return ""

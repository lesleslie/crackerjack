"""Centralized output path management for adapter files.

This module provides utilities for managing adapter output files in a centralized
location (.crackerjack/outputs/) to keep the project root clean.

ACB Patterns:
- Pure utility module (no DI registration needed)
- Simple, focused responsibility
- Consistent path management across all adapters
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AdapterOutputPaths:
    """Centralized path manager for adapter output files.

    All adapter output files (JSON results, logs, temporary files) are stored in:
    .crackerjack/outputs/

    This keeps the project root clean and makes it easy to:
    - Add to .gitignore
    - Clean up old files
    - Find all adapter outputs in one place
    """

    # Base directory for all adapter outputs
    OUTPUTS_DIR = ".crackerjack/outputs"

    @classmethod
    def get_output_dir(cls, adapter_name: str | None = None) -> Path:
        """Get the output directory for an adapter.

        Args:
            adapter_name: Optional adapter-specific subdirectory

        Returns:
            Path to output directory (created if doesn't exist)
        """
        base_dir = Path.cwd() / cls.OUTPUTS_DIR

        if adapter_name:
            output_dir = base_dir / adapter_name
        else:
            output_dir = base_dir

        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    @classmethod
    def get_output_file(
        cls,
        adapter_name: str,
        filename: str,
        timestamped: bool = False,
    ) -> Path:
        """Get path for an adapter output file.

        Args:
            adapter_name: Name of the adapter (e.g., 'complexipy', 'bandit')
            filename: Base filename (e.g., 'results.json')
            timestamped: If True, add timestamp to filename

        Returns:
            Full path to output file in .crackerjack/outputs/adapter_name/

        Examples:
            >>> AdapterOutputPaths.get_output_file("complexipy", "results.json")
            PosixPath('.crackerjack/outputs/complexipy/results.json')

            >>> AdapterOutputPaths.get_output_file(
            ...     "bandit", "scan.json", timestamped=True
            ... )
            PosixPath('.crackerjack/outputs/bandit/scan_2025_12_09__12:34:56.json')
        """
        output_dir = cls.get_output_dir(adapter_name)

        if timestamped:
            # Add timestamp before extension
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            timestamp = datetime.now().strftime("%Y_%m_%d__%H:%M:%S")
            filename = f"{stem}_{timestamp}{suffix}"

        return output_dir / filename

    @classmethod
    def get_latest_output(
        cls, adapter_name: str, pattern: str = "*.json"
    ) -> Path | None:
        """Get the most recently modified output file for an adapter.

        Args:
            adapter_name: Name of the adapter
            pattern: Glob pattern for files (default: *.json)

        Returns:
            Path to most recent file, or None if no files found
        """
        output_dir = cls.get_output_dir(adapter_name)

        if not output_dir.exists():
            return None

        files = sorted(
            output_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        return files[0] if files else None

    @classmethod
    def cleanup_old_outputs(
        cls,
        adapter_name: str,
        pattern: str = "*.json",
        keep_latest: int = 5,
    ) -> int:
        """Remove old output files, keeping only the most recent ones.

        Args:
            adapter_name: Name of the adapter
            pattern: Glob pattern for files (default: *.json)
            keep_latest: Number of most recent files to keep

        Returns:
            Number of files deleted
        """
        output_dir = cls.get_output_dir(adapter_name)

        if not output_dir.exists():
            return 0

        files = sorted(
            output_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Keep the N most recent files, delete the rest
        files_to_delete = files[keep_latest:]
        deleted_count = 0

        for file_path in files_to_delete:
            try:
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old output file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} old {adapter_name} output files, "
                f"kept {keep_latest} most recent"
            )

        return deleted_count

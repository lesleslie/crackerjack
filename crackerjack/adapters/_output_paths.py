from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AdapterOutputPaths:
    OUTPUTS_DIR = ".crackerjack/outputs"

    @classmethod
    def get_output_dir(cls, adapter_name: str | None = None) -> Path:
        base_dir = Path.cwd() / cls.OUTPUTS_DIR

        if adapter_name:
            output_dir = base_dir / adapter_name
        else:
            output_dir = base_dir

        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    @classmethod
    def get_output_file(
        cls,
        adapter_name: str,
        filename: str,
        timestamped: bool = False,
    ) -> Path:
        output_dir = cls.get_output_dir(adapter_name)

        if timestamped:
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            timestamp = datetime.now().strftime("%Y_%m_%d__%H:%M:%S")
            filename = f"{stem}_{timestamp}{suffix}"

        return output_dir / filename

    @classmethod
    def get_latest_output(
        cls, adapter_name: str, pattern: str = "*.json"
    ) -> Path | None:
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
        output_dir = cls.get_output_dir(adapter_name)

        if not output_dir.exists():
            return 0

        files = sorted(
            output_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

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

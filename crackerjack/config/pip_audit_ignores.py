from __future__ import annotations

from pathlib import Path


IGNORED_VULNERABILITY_IDS: tuple[str, ...] = (
    "CVE-2025-53000",
    "CVE-2025-14009",
    "CVE-2025-69872",
    "CVE-2026-0994",
    "PYSEC-2024-277",
    "PYSEC-2025-183",
    "PYSEC-2025-211",
    "PYSEC-2025-212",
    "PYSEC-2025-213",
    "PYSEC-2025-214",
    "PYSEC-2025-215",
    "PYSEC-2025-216",
    "PYSEC-2025-217",
    "PYSEC-2025-218",
    "PYSEC-2026-89",
    "PYSEC-2026-97",
    "PYSEC-2025-144",
    "PYSEC-2025-145",
    "PYSEC-2025-146",
    "PYSEC-2025-147",
    "PYSEC-2026-101",
    "PYSEC-2026-102",
    "CVE-2026-12243",
    "CVE-2026-25990",
    "CVE-2026-40192",
    "CVE-2026-42308",
    "CVE-2026-42309",
    "CVE-2026-42310",
    "CVE-2026-42311",
    "CVE-2026-54293",
    "GHSA-p4gq-832x-fm9v",
    "PYSEC-2026-597",
)


def load_merged_ignores(project_dir: Path | None = None) -> list[str]:
    ids = set(IGNORED_VULNERABILITY_IDS)

    if project_dir is not None:
        pyproject = Path(project_dir) / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib

                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError):


                return sorted(ids)

            project_ignores = (
                data.get("tool", {}).get("pip-audit", {}).get("ignore-vuln", [])
            )
            if isinstance(project_ignores, list):
                for vid in project_ignores:
                    if isinstance(vid, str) and vid:
                        ids.add(vid)

    return sorted(ids)

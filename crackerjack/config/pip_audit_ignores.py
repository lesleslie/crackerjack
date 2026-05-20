from __future__ import annotations

# Vulnerability IDs ignored by pip-audit across all execution paths.
# Add new entries here only — do not duplicate in tool_commands.py or pip_audit.py.
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
    # markdown 3.10.2 is fixed; OSV entry lacks fix_versions so pip-audit
    # cannot confirm it — false positive until the OSV record is updated.
    "PYSEC-2026-89",
)

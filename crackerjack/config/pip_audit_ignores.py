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
    # nltk (via llama-index-core): filestring() path traversal — no fix version upstream
    "PYSEC-2026-97",
    # ollama Python client (via llama-index-llms/embeddings-ollama): these CVEs describe
    # server-side vulnerabilities in the Ollama binary (GGUF parsing, DoS via /api/pull),
    # not the Python client library — no fix version available for the client package
    "PYSEC-2025-144",
    "PYSEC-2025-145",
    "PYSEC-2025-146",
    "PYSEC-2025-147",
    "PYSEC-2026-101",
    "PYSEC-2026-102",
    # Pillow (via mahavishnu[automation] optional extra): CVEs fixed in 12.2.0, but
    # fastembed 0.3-0.7.4 pins pillow<12.0 — cannot upgrade until fastembed 0.8+
    # is compatible with session-buddy's onnxruntime constraint
    "CVE-2026-25990",
    "CVE-2026-40192",
    "CVE-2026-42308",
    "CVE-2026-42309",
    "CVE-2026-42310",
    "CVE-2026-42311",
)

from __future__ import annotations

from pathlib import Path

# CVE ignore list for ``pip-audit`` invoked through ``crackerjack run``.
#
# Each entry is a single canonical vulnerability ID (CVE or PYSEC alias).
# The synchronization test in ``tests/config/test_pip_audit_ignores.py``
# enforces that every entry here is passed as ``--ignore-vuln`` to
# ``pip-audit`` — adding a new ID to this tuple is the canonical way to
# suppress a known-failing-fast-hook vuln across the Bodai ecosystem.
#
# Add nltk transitive-only CVEs alongside the existing nltk pair.
# nltk is a transitive dep of ``llama-index-core`` and ``safety``; no
# Bodai source file imports ``nltk`` so ``nltk.data.load()`` is not
# reachable. Latest published nltk on PyPI is 3.9.4 (= what we lock);
# no upstream fix is available, so the only durable mitigation is to
# suppress the audit at the source.
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
    """Return canonical ignores unioned with the audited project's overrides.

    Two layers of ignores are honored:

    1. **Canonical layer** — ``IGNORED_VULNERABILITY_IDS`` in this module.
       Always applied; covers vulns that affect every Bodai repo.
    2. **Project layer** — ``[tool.pip-audit] ignore-vuln = [...]`` in the
       audited project's ``pyproject.toml``. Read when ``project_dir`` is
       given; lets a single repo opt out without forking crackerjack.

    Union semantics: an ID present in *either* layer is filtered. Project
    IDs don't override canonical IDs — they extend them. This is by
    design: a typo in a project layer can't accidentally *un*-suppress a
    canonical ignore.

    Why order matters
    -----------------
    We sort the result so that downstream ``--ignore-vuln`` flag ordering
    is deterministic across runs. That keeps test outputs stable and
    makes the lockfile reproducible.

    Why a function (not a module-level cached value)
    ------------------------------------------------
    The CWD at import time may differ from the CWD at hook execution
    time, and a long-running MCP server can audit multiple projects in
    one session. Resolve ``project_dir`` lazily at each call.
    """
    ids = set(IGNORED_VULNERABILITY_IDS)

    if project_dir is not None:
        pyproject = Path(project_dir) / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib

                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError):
                # Malformed project pyproject shouldn't kill the gate;
                # fall back to canonical-only.
                return sorted(ids)

            project_ignores = (
                data.get("tool", {}).get("pip-audit", {}).get("ignore-vuln", [])
            )
            if isinstance(project_ignores, list):
                for vid in project_ignores:
                    if isinstance(vid, str) and vid:
                        ids.add(vid)

    return sorted(ids)

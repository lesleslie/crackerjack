"""SAST (Static Application Security Testing) adapters for ACB QA framework.

This package contains adapters for static application security testing tools
that analyze source code for vulnerabilities, security anti-patterns, and
exploitable weaknesses.

Tools:
- Semgrep: Multi-language static analysis with custom rules (recommended)
- Bandit: Python-specific security linter (legacy)
- Pyscn: Python security static analyzer (experimental)

Protocol:
- SASTAdapterProtocol: Protocol interface for all SAST adapters
"""

from crackerjack.adapters.sast._base import SASTAdapter, SASTAdapterProtocol
from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings
from crackerjack.adapters.sast.pyscn import PyscnAdapter, PyscnSettings
from crackerjack.adapters.sast.semgrep import SemgrepAdapter, SemgrepSettings

__all__ = [
    # Protocol
    "SASTAdapter",
    "SASTAdapterProtocol",
    # Adapters
    "BanditAdapter",
    "BanditSettings",
    "PyscnAdapter",
    "PyscnSettings",
    "SemgrepAdapter",
    "SemgrepSettings",
]

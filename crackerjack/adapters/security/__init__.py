"""Security adapters for secret leak prevention.

This package contains adapters for detecting hardcoded secrets and credentials
in code repositories to prevent security breaches.

Tools:
- Gitleaks: Git-aware secrets/credentials detection with redaction

Note: SAST tools (Bandit, Semgrep, Pyscn) have been moved to crackerjack.adapters.sast
"""

from crackerjack.adapters.security.gitleaks import GitleaksAdapter, GitleaksSettings

__all__ = [
    "GitleaksAdapter",
    "GitleaksSettings",
]

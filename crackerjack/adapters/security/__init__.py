"""Security adapters for vulnerability and secret detection.

Adapters:
- bandit: Python security vulnerability scanner
- gitleaks: Secret and credential detection in git history
- pyscn: Python static code security analyzer (experimental)
"""

# ACB will auto-discover these adapters via depends.set() in module files
# No explicit imports needed here

__all__ = []

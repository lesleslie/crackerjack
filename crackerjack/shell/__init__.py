"""Crackerjack admin shell with quality management formatters and helpers.

This module extends the Oneiric AdminShell with Crackerjack-specific functionality
for quality checks, testing, linting, and security scanning.

Example:
    >>> from crackerjack.shell import CrackerjackShell
    >>> from crackerjack.config import load_settings
    >>> settings = load_settings()
    >>> shell = CrackerjackShell(settings)
    >>> shell.start()
"""

from .adapter import CrackerjackShell

__all__ = ["CrackerjackShell"]

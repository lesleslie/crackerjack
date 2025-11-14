"""Bandit security scanner output parsing patterns.

This module provides regex patterns for parsing Bandit security analysis tool output,
including issue detection, location information, confidence, and severity levels.
"""

from ..core import ValidatedPattern

PATTERNS = {
    "bandit_confidence": ValidatedPattern(
        name="bandit_confidence",
        pattern=r"Confidence: (\w+)",
        replacement=r"Confidence Level: \1",
        description="Parse bandit confidence level for security issues",
        test_cases=[
            ("Confidence: HIGH", "Confidence Level: HIGH"),
            ("Confidence: MEDIUM", "Confidence Level: MEDIUM"),
            ("Confidence: LOW", "Confidence Level: LOW"),
        ],
    ),
    "bandit_issue": ValidatedPattern(
        name="bandit_issue",
        pattern=r">> Issue: \[([A-Z]\d+): \w+\] (.+)",
        replacement=r"Security Issue [\1]: \2",
        description="Parse bandit security issue output with code and message",
        test_cases=[
            (
                ">> Issue: [B602: shell_injection] Use of shell=True",
                "Security Issue [B602]: Use of shell=True",
            ),
            (
                ">> Issue: [B404: blacklist] Consider possible security implications",
                "Security Issue [B404]: Consider possible security implications",
            ),
            (
                ">> Issue: [B301: pickle] Pickle library detected",
                "Security Issue [B301]: Pickle library detected",
            ),
        ],
    ),
    "bandit_location": ValidatedPattern(
        name="bandit_location",
        pattern=r"Location: (.+?): (\d+): (\d+)",
        replacement=r"Location: File \1, Line \2, Column \3",
        description="Parse bandit location information for security issues",
        test_cases=[
            (
                "Location: src/main.py: 42: 10",
                "Location: File src/main.py, Line 42, Column 10",
            ),
            (
                "Location: /app/security.py: 123: 5",
                "Location: File /app/security.py, Line 123, Column 5",
            ),
            (
                "Location: crackerjack/core.py: 999: 80",
                "Location: File crackerjack/core.py, Line 999, Column 80",
            ),
        ],
    ),
    "bandit_severity": ValidatedPattern(
        name="bandit_severity",
        pattern=r"Severity: (\w+)",
        replacement=r"Severity Level: \1",
        description="Parse bandit severity level for security issues",
        test_cases=[
            ("Severity: HIGH", "Severity Level: HIGH"),
            ("Severity: MEDIUM", "Severity Level: MEDIUM"),
            ("Severity: LOW", "Severity Level: LOW"),
        ],
    ),
}

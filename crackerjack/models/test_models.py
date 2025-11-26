from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestFailure:
    """Structured representation of a test failure."""

    test_name: str
    """Full test node ID (e.g., tests/test_foo.py::TestClass::test_method)"""

    status: str
    """Test status: FAILED, ERROR, or XFAIL"""

    location: str
    """File path and line number (e.g., tests/test_foo.py:42)"""

    traceback: list[str] = field(default_factory=list)
    """Full traceback lines"""

    assertion: str | None = None
    """Assertion error message if present"""

    captured_stdout: str | None = None
    """Captured stdout during test execution"""

    captured_stderr: str | None = None
    """Captured stderr during test execution"""

    duration: float | None = None
    """Test execution duration in seconds"""

    short_summary: str | None = None
    """One-line failure summary"""

    locals_context: dict[str, Any] = field(default_factory=dict)
    """Local variables at failure point (in -vvv mode)"""

    def get_file_path(self) -> str:
        """Extract file path from location."""
        if ":" in self.location:
            return self.location.split(":")[0]
        return self.location

    def get_line_number(self) -> int | None:
        """Extract line number from location."""
        if ":" in self.location:
            try:
                return int(self.location.split(":")[1])
            except (ValueError, IndexError):
                return None
        return None

    def get_relevant_traceback(self, max_lines: int = 15) -> list[str]:
        """Get most relevant traceback lines (last N lines)."""
        return (
            self.traceback[-max_lines:]
            if len(self.traceback) > max_lines
            else self.traceback
        )

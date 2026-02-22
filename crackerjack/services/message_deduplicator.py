"""Message deduplication service for debug output.

Collects duplicate log/output messages and displays them once with a count.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MessageDeduplicator:
    """Collects and deduplicates messages for cleaner output.

    Usage:
        dedup = MessageDeduplicator()
        dedup.add_message("Plan execution failed")
        dedup.add_message("Plan execution failed")
        dedup.add_message("Plan execution failed")
        # ... later ...
        dedup.print_summary(console)
        # Output: "Plan execution failed (appeared 3 times)"
    """

    enabled: bool = True
    messages: Counter = field(default_factory=Counter)
    first_occurrence: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_message(
        self,
        message: str,
        level: str = "info",
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Add a message to the deduplicator.

        Args:
            message: The message text
            level: Log level (info, warning, error, debug)
            context: Optional context metadata

        Returns:
            True if this is the first occurrence (should print immediately)
        """
        if not self.enabled:
            return True

        # Create a key from message and level
        key = f"{level}:{message}"

        self.messages[key] += 1

        # Store first occurrence details
        if key not in self.first_occurrence:
            self.first_occurrence[key] = {
                "message": message,
                "level": level,
                "context": context or {},
                "count": 1,
            }
            return True  # First occurrence

        return False  # Duplicate

    def should_show(self, message: str, level: str = "info") -> bool:
        """Check if a message should be shown (first occurrence).

        Args:
            message: The message text
            level: Log level

        Returns:
            True if this is the first time seeing this message
        """
        if not self.enabled:
            return True

        key = f"{level}:{message}"
        return self.messages[key] == 0

    def get_duplicates(self) -> list[dict[str, Any]]:
        """Get all messages that appeared more than once.

        Returns:
            List of duplicate message info dicts
        """
        duplicates = []
        for key, count in self.messages.items():
            if count > 1 and key in self.first_occurrence:
                info = self.first_occurrence[key].copy()
                info["count"] = count
                duplicates.append(info)
        return duplicates

    def get_summary(self) -> str:
        """Get a summary string of duplicate messages.

        Returns:
            Formatted summary of duplicates
        """
        duplicates = self.get_duplicates()
        if not duplicates:
            return ""

        lines = ["\n📊 Duplicate Message Summary:"]
        for dup in sorted(duplicates, key=lambda x: x["count"], reverse=True):
            count = dup["count"]
            message = (
                dup["message"][:60] + "..."
                if len(dup["message"]) > 60
                else dup["message"]
            )
            lines.append(
                f'  [{dup["level"].upper()}] "{message}" - appeared {count} times'
            )

        return "\n".join(lines)

    def print_summary(self, console: Any) -> None:
        """Print the duplicate summary to a rich console.

        Args:
            console: Rich Console instance
        """
        summary = self.get_summary()
        if summary:
            try:
                from rich.panel import Panel

                console.print(
                    Panel(summary, title="Message Deduplication", border_style="dim")
                )
            except ImportError:
                console.print(summary)

    def reset(self) -> None:
        """Clear all tracked messages."""
        self.messages.clear()
        self.first_occurrence.clear()

    @property
    def total_messages(self) -> int:
        """Total number of messages tracked."""
        return sum(self.messages.values())

    @property
    def unique_messages(self) -> int:
        """Number of unique messages."""
        return len(self.messages)

    @property
    def duplicate_count(self) -> int:
        """Number of duplicate occurrences (total - unique)."""
        return self.total_messages - self.unique_messages


# Global instance for convenience
_deduplicator: MessageDeduplicator | None = None


def get_deduplicator() -> MessageDeduplicator:
    """Get or create the global message deduplicator."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator()
    return _deduplicator


def reset_deduplicator() -> None:
    """Reset the global deduplicator."""
    global _deduplicator
    if _deduplicator:
        _deduplicator.reset()
    else:
        _deduplicator = MessageDeduplicator()

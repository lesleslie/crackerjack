
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MessageDeduplicator:

    enabled: bool = True
    messages: Counter = field(default_factory=Counter)
    first_occurrence: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_message(
        self,
        message: str,
        level: str = "info",
        context: dict[str, Any] | None = None,
    ) -> bool:
        if not self.enabled:
            return True


        key = f"{level}:{message}"

        self.messages[key] += 1


        if key not in self.first_occurrence:
            self.first_occurrence[key] = {
                "message": message,
                "level": level,
                "context": context or {},
                "count": 1,
            }
            return True

        return False

    def should_show(self, message: str, level: str = "info") -> bool:
        if not self.enabled:
            return True

        key = f"{level}:{message}"
        return self.messages[key] == 0

    def get_duplicates(self) -> list[dict[str, Any]]:
        duplicates = []
        for key, count in self.messages.items():
            if count > 1 and key in self.first_occurrence:
                info = self.first_occurrence[key].copy()
                info["count"] = count
                duplicates.append(info)
        return duplicates

    def get_summary(self) -> str:
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
        self.messages.clear()
        self.first_occurrence.clear()

    @property
    def total_messages(self) -> int:
        return sum(self.messages.values())

    @property
    def unique_messages(self) -> int:
        return len(self.messages)

    @property
    def duplicate_count(self) -> int:
        return self.total_messages - self.unique_messages


_deduplicator: MessageDeduplicator | None = None


def get_deduplicator() -> MessageDeduplicator:
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator()
    return _deduplicator


def reset_deduplicator() -> None:
    global _deduplicator
    if _deduplicator:
        _deduplicator.reset()
    else:
        _deduplicator = MessageDeduplicator()

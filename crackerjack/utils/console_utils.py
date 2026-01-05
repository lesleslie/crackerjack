from __future__ import annotations

from crackerjack.config import get_console_width


def separator(char: str = "-", width: int | None = None) -> str:
    w = width if isinstance(width, int) and width > 0 else get_console_width()
    return char * w

"""Crackerjack Console - Async wrapper around Rich Console.

This module provides a protocol-compliant console implementation that supports
both synchronous and asynchronous printing, following Crackerjack's
protocol-based design philosophy.
"""

import typing as t

from rich.console import Console as RichConsole

from crackerjack.models.protocols import ConsoleInterface


class CrackerjackConsole(RichConsole, ConsoleInterface):
    """Async-enabled console wrapper extending Rich Console.

    This class extends Rich's Console with async capabilities while
    maintaining full compatibility with the ConsoleInterface protocol.

    Example:
        console = CrackerjackConsole()

        # Synchronous print (delegates to Rich)
        console.print("[green]Hello[/green]")

        # Async print (wraps Rich's sync print)
        await console.aprint("[blue]World[/blue]")
    """

    async def aprint(self, *args: t.Any, **kwargs: t.Any) -> None:
        """Async print method - wraps Rich's synchronous print.

        Rich's print() is thread-safe and works fine in async contexts,
        so this simply wraps it for async/await syntax compatibility.

        Args:
            *args: Objects to print (same as Rich Console.print)
            **kwargs: Formatting options (same as Rich Console.print)
        """
        # Rich's print is safe in async contexts - just wrap for await syntax
        self.print(*args, **kwargs)

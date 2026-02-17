import typing as t

from rich.console import Console as RichConsole

from crackerjack.models.protocols import ConsoleInterface


class CrackerjackConsole(RichConsole, ConsoleInterface):
    async def aprint(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.print(*args, **kwargs)

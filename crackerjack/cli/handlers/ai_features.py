"""CLI handlers for AI-powered features (contextual AI assistant)"""

import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends


@depends.inject  # type: ignore[misc]
def handle_contextual_ai(
    contextual_ai: bool,
    ai_recommendations: int,
    ai_help_query: str | None,
    console: Inject[Console],
) -> bool:
    if not contextual_ai and not ai_help_query:
        return True

    from crackerjack.services.ai.contextual_ai_assistant import ContextualAIAssistant

    console.print("[cyan]🤖[/cyan] Running contextual AI assistant analysis...")

    try:

        class FileSystemImpl:
            def read_file(self, path: str | t.Any) -> str:
                return Path(path).read_text()

            def write_file(self, path: str | t.Any, content: str) -> None:
                Path(path).write_text(content)

            def exists(self, path: str | t.Any) -> bool:
                return Path(path).exists()

            def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
                Path(path).mkdir(parents=parents, exist_ok=True)

        filesystem = FileSystemImpl()
        assistant = ContextualAIAssistant(filesystem)

        if ai_help_query:
            help_response = assistant.get_quick_help(ai_help_query)
            console.print(f"\n[blue]🔍[/blue] AI Help for '{ai_help_query}':")
            console.print(help_response)
            return False

        console.print(
            "[blue]🧠[/blue] Analyzing project context for AI recommendations..."
        )
        recommendations = assistant.get_contextual_recommendations(ai_recommendations)

        if recommendations:
            assistant.display_recommendations(recommendations)
        else:
            console.print("[green]✨[/green] Great job! No immediate recommendations")

        return False

    except Exception as e:
        console.print(f"[red]❌[/red] Contextual AI error: {e}")
        return False

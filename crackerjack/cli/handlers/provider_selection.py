import logging
import os
import typing as t
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from crackerjack.adapters.ai.registry import (
    ProviderFactory,
    ProviderID,
)
from crackerjack.config import CrackerjackSettings, load_settings

logger = logging.getLogger(__name__)


class ProviderSelectionCLI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.factory = ProviderFactory()

    async def run_interactive_selection(self) -> None:
        self._print_header()

        provider_id = self._select_provider()

        self._show_provider_details(provider_id)

        if not self._confirm_selection(provider_id):
            self.console.print("[yellow]Selection cancelled.[/yellow]")
            return

        await self._offer_connection_test(provider_id)

        self._save_provider_selection(provider_id)

        self.console.print(
            f"[green]✓ Provider '{provider_id.value}' configured successfully![/green]",
        )

    def _print_header(self) -> None:
        header = Panel(
            "[bold cyan]AI Provider Selection[/bold cyan]\n\n"
            "Configure the AI provider for crackerjack's code fixing features.\n"
            "Current options: Claude, Qwen, Ollama",
            title="Crackerjack Configuration",
            border_style="cyan",
        )
        self.console.print(header)
        self.console.print()

    def _select_provider(self) -> ProviderID:
        table = Table(title="Available Providers")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Provider", style="green")
        table.add_column("Description", style="white")
        table.add_column("Cost", style="yellow")
        table.add_column("API Key", style="red")

        providers = self.factory.list_providers()

        for idx, info in enumerate(providers, 1):
            api_key_status = (
                "[red]Required[/red]"
                if info.requires_api_key
                else "[green]None[/green]"
            )
            table.add_row(
                str(idx),
                info.name,
                info.description,
                info.cost_tier,
                api_key_status,
            )

        self.console.print(table)
        self.console.print()

        choice = Prompt.ask(
            "[bold]Select a provider[/bold]",
            choices=[str(i) for i in range(1, len(providers) + 1)],
            default="1",
        )

        selected_provider = providers[int(choice) - 1]
        return selected_provider.id

    def _show_provider_details(self, provider_id: ProviderID) -> None:
        info = self.factory.get_provider_info(provider_id)

        details = Table(title=f"{info.name} Details", show_header=False)
        details.add_column("Field", style="cyan")
        details.add_column("Value", style="white")

        details.add_row("Description", info.description)
        details.add_row("Default Model", info.default_model)
        details.add_row("Cost Tier", info.cost_tier)
        details.add_row("API Key Required", "Yes" if info.requires_api_key else "No")
        details.add_row("Setup Guide", info.setup_url)

        self.console.print(details)
        self.console.print()

        if info.requires_api_key:
            env_var = self._get_api_key_env_var(provider_id)
            self.console.print(
                f"[yellow]Required: Set {env_var} environment variable[/yellow]",
            )

            if os.getenv(env_var):
                self.console.print(f"[green]✓ {env_var} is already set[/green]")
            else:
                self.console.print(f"[red]✗ {env_var} is not set[/red]")
        else:
            self.console.print(
                "[green]✓ No API key required (local execution)[/green]",
            )

        self.console.print()

    def _confirm_selection(self, provider_id: ProviderID) -> bool:
        info = self.factory.get_provider_info(provider_id)

        return Confirm.ask(
            f"[bold]Configure crackerjack to use {info.name}?[/bold]",
            default=True,
        )

    async def _offer_connection_test(self, provider_id: ProviderID) -> None:
        if not Confirm.ask("[bold]Test connection to provider?[/bold]", default=False):
            return

        self.console.print("[cyan]Testing connection...[/cyan]")

        try:
            provider = self.factory.create_provider(provider_id)

            await provider.init()

            result = await provider.fix_code_issue(
                file_path="test.py",
                issue_description="Test connection",
                code_context="print('hello')\n",
                fix_type="test",
                max_retries=1,
            )

            if result.get("success"):
                self.console.print("[green]✓ Connection successful![/green]")
            else:
                error = result.get("error", "Unknown error")
                self.console.print(f"[red]✗ Connection failed: {error}[/red]")

        except Exception as e:
            self.console.print(f"[red]✗ Connection test failed: {e}[/red]")
            logger.exception("Connection test failed")

    def _save_provider_selection(self, provider_id: ProviderID) -> None:
        settings = load_settings(CrackerjackSettings)

        settings.ai.ai_provider = provider_id.value  # type: ignore

        local_settings_path = Path("settings/local.yaml")

        local_settings_path.parent.mkdir(exist_ok=True)

        import yaml

        existing_config: dict[str, t.Any] = {}
        if local_settings_path.exists():
            with local_settings_path.open("r") as f:
                existing_config = yaml.safe_load(f) or {}

        if "ai" not in existing_config:
            existing_config["ai"] = {}

        existing_config["ai"]["ai_provider"] = provider_id.value

        with local_settings_path.open("w") as f:
            yaml.dump(existing_config, f, default_flow_style=False)

        self.console.print(
            f"[green]✓ Settings saved to {local_settings_path}[/green]",
        )

    def _get_api_key_env_var(self, provider_id: ProviderID) -> str:
        env_vars = {
            ProviderID.CLAUDE: "ANTHROPIC_API_KEY",
            ProviderID.QWEN: "QWEN_API_KEY",
            ProviderID.OLLAMA: "",
        }
        return env_vars.get(provider_id, "")


async def handle_select_provider() -> None:
    console = Console()
    cli = ProviderSelectionCLI(console)
    await cli.run_interactive_selection()

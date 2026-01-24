"""Interactive provider selection CLI handler."""

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
    """Interactive CLI for selecting and configuring AI providers."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize provider selection CLI.

        Args:
            console: Rich console instance (optional)
        """
        self.console = console or Console()
        self.factory = ProviderFactory()

    async def run_interactive_selection(self) -> None:
        """Run interactive provider selection flow.

        Flow:
        1. List available providers
        2. User selects provider
        3. Show provider details
        4. Test connection (optional)
        5. Save selection to settings/local.yaml
        """
        self._print_header()

        # Step 1: Show available providers
        provider_id = self._select_provider()

        # Step 2: Show provider details
        self._show_provider_details(provider_id)

        # Step 3: Confirm selection
        if not self._confirm_selection(provider_id):
            self.console.print("[yellow]Selection cancelled.[/yellow]")
            return

        # Step 4: Test connection (optional)
        await self._offer_connection_test(provider_id)

        # Step 5: Save settings
        self._save_provider_selection(provider_id)

        self.console.print(
            f"[green]✓ Provider '{provider_id.value}' configured successfully![/green]",
        )

    def _print_header(self) -> None:
        """Print selection header."""
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
        """Display provider list and get user selection.

        Returns:
            Selected provider ID
        """
        # Create provider table
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

        # Get user selection
        choice = Prompt.ask(
            "[bold]Select a provider[/bold]",
            choices=[str(i) for i in range(1, len(providers) + 1)],
            default="1",
        )

        selected_provider = providers[int(choice) - 1]
        return selected_provider.id

    def _show_provider_details(self, provider_id: ProviderID) -> None:
        """Display detailed information about selected provider.

        Args:
            provider_id: Selected provider
        """
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

        # Show environment variable requirements
        if info.requires_api_key:
            env_var = self._get_api_key_env_var(provider_id)
            self.console.print(
                f"[yellow]Required: Set {env_var} environment variable[/yellow]",
            )

            # Check if already set
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
        """Confirm provider selection with user.

        Args:
            provider_id: Selected provider

        Returns:
            True if confirmed, False otherwise
        """
        info = self.factory.get_provider_info(provider_id)

        return Confirm.ask(
            f"[bold]Configure crackerjack to use {info.name}?[/bold]",
            default=True,
        )

    async def _offer_connection_test(self, provider_id: ProviderID) -> None:
        """Offer to test provider connection.

        Args:
            provider_id: Selected provider
        """
        if not Confirm.ask("[bold]Test connection to provider?[/bold]", default=False):
            return

        self.console.print("[cyan]Testing connection...[/cyan]")

        try:
            # Create provider instance
            provider = self.factory.create_provider(provider_id)

            # Initialize
            await provider.init()

            # Test with a simple request
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
        """Save provider selection to settings/local.yaml.

        Args:
            provider_id: Selected provider
        """
        # Load current settings
        settings = load_settings(CrackerjackSettings)

        # Update provider selection
        settings.ai.ai_provider = provider_id.value  # type: ignore

        # Save to local.yaml
        local_settings_path = Path("settings/local.yaml")

        # Ensure settings directory exists
        local_settings_path.parent.mkdir(exist_ok=True)

        # Load existing local.yaml if it exists
        import yaml

        existing_config: dict[str, t.Any] = {}
        if local_settings_path.exists():
            with local_settings_path.open("r") as f:
                existing_config = yaml.safe_load(f) or {}

        # Update AI settings
        if "ai" not in existing_config:
            existing_config["ai"] = {}

        existing_config["ai"]["ai_provider"] = provider_id.value

        # Write updated config
        with local_settings_path.open("w") as f:
            yaml.dump(existing_config, f, default_flow_style=False)

        self.console.print(
            f"[green]✓ Settings saved to {local_settings_path}[/green]",
        )

    def _get_api_key_env_var(self, provider_id: ProviderID) -> str:
        """Get environment variable name for provider's API key.

        Args:
            provider_id: Provider identifier

        Returns:
            Environment variable name
        """
        env_vars = {
            ProviderID.CLAUDE: "ANTHROPIC_API_KEY",
            ProviderID.QWEN: "QWEN_API_KEY",
            ProviderID.OLLAMA: "",  # No API key required
        }
        return env_vars.get(provider_id, "")


# CLI command handler
async def handle_select_provider() -> None:
    """Handle --select-provider CLI command."""
    console = Console()
    cli = ProviderSelectionCLI(console)
    await cli.run_interactive_selection()

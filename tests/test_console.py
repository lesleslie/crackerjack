"""Tests for console module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.core.console import CrackerjackConsole


class TestCrackerjackConsole:
    """Tests for CrackerjackConsole class."""

    @pytest.fixture
    def console(self) -> CrackerjackConsole:
        """Create a CrackerjackConsole instance for testing."""
        return CrackerjackConsole()

    def test_inheritance(self, console: CrackerjackConsole) -> None:
        """Test CrackerjackConsole inherits from RichConsole."""
        assert isinstance(console, Console)

    def test_inheritance_from_console_interface(self, console: CrackerjackConsole) -> None:
        """Test CrackerjackConsole satisfies ConsoleInterface protocol."""
        from crackerjack.models.protocols import ConsoleInterface
        assert isinstance(console, ConsoleInterface)

    @pytest.mark.asyncio
    async def test_aprint_calls_print(self, console: CrackerjackConsole) -> None:
        """Test aprint calls the parent's print method."""
        with patch.object(console, "print") as mock_print:
            await console.aprint("Test message")
            mock_print.assert_called_once_with("Test message")

    @pytest.mark.asyncio
    async def test_aprint_with_kwargs(self, console: CrackerjackConsole) -> None:
        """Test aprint passes through kwargs to print."""
        with patch.object(console, "print") as mock_print:
            await console.aprint("Test", style="bold red", justify="center")
            mock_print.assert_called_once_with("Test", style="bold red", justify="center")

    @pytest.mark.asyncio
    async def test_aprint_multiple_args(self, console: CrackerjackConsole) -> None:
        """Test aprint with multiple positional arguments."""
        with patch.object(console, "print") as mock_print:
            await console.aprint("Arg1", "Arg2", "Arg3")
            mock_print.assert_called_once_with("Arg1", "Arg2", "Arg3")

    @pytest.mark.asyncio
    async def test_aprint_returns_none(self, console: CrackerjackConsole) -> None:
        """Test aprint returns None."""
        result = await console.aprint("Test")
        assert result is None

    @pytest.mark.asyncio
    async def test_aprint_empty_call(self, console: CrackerjackConsole) -> None:
        """Test aprint with no arguments."""
        with patch.object(console, "print") as mock_print:
            await console.aprint()
            mock_print.assert_called_once_with()


class TestConsoleInterfaceProtocol:
    """Tests for ConsoleInterface protocol compliance."""

    def test_crackerjack_console_satisfies_protocol(self) -> None:
        """Test that CrackerjackConsole satisfies ConsoleInterface."""
        from crackerjack.models.protocols import ConsoleInterface
        console = CrackerjackConsole()
        # Protocol is runtime checkable, so this should work
        assert isinstance(console, ConsoleInterface)

    def test_protocol_requirements(self) -> None:
        """Test that the protocol has required methods."""
        from crackerjack.models.protocols import ConsoleInterface
        # ConsoleInterface requires print and input methods (and optionally aprint)
        assert hasattr(ConsoleInterface, "print")
        assert hasattr(ConsoleInterface, "input")
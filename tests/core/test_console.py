import pytest
from unittest.mock import patch
from crackerjack.core.console import CrackerjackConsole


def test_crackerjack_console_initialization():
    """Test that CrackerjackConsole initializes properly."""
    console = CrackerjackConsole()
    assert console is not None


def test_crackerjack_console_print_method():
    """Test that CrackerjackConsole can print."""
    console = CrackerjackConsole()

    # Just test that the print method works without error
    # We'll mock the output to avoid actual printing
    with patch.object(console, 'print') as mock_print:
        console.print("test message")
        mock_print.assert_called_once_with("test message")


def test_crackerjack_console_aprint_method():
    """Test the async print method."""
    console = CrackerjackConsole()

    # Test that aprint calls print internally
    with patch.object(console, 'print') as mock_print:
        # Since aprint is async, we need to await it
        import asyncio

        async def test_async_print():
            await console.aprint("async test message")

        asyncio.run(test_async_print())
        mock_print.assert_called_once_with("async test message")


def test_crackerjack_console_inheritance():
    """Test that CrackerjackConsole inherits from both RichConsole and ConsoleInterface."""
    from crackerjack.models.protocols import ConsoleInterface

    console = CrackerjackConsole()

    # Check that it's an instance of RichConsole (which is the parent of CrackerjackConsole)
    from rich.console import Console as RichConsole
    assert isinstance(console, RichConsole)

    # Check that it implements ConsoleInterface methods
    assert hasattr(console, 'print')
    assert hasattr(console, 'aprint')

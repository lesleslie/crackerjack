import pytest
from unittest.mock import MagicMock
from crackerjack.documentation.reference_generator import (
    CommandReference,
    CommandInfo,
    ParameterInfo,
    ReferenceGenerator,
    ReferenceFormat,
)
from crackerjack.models.protocols import ConfigManagerProtocol, LoggerProtocol


@pytest.mark.unit
class TestReferenceGenerator:
    """Unit tests for ReferenceGenerator and CommandReference classes."""

    @pytest.fixture
    def mock_config_manager(self):
        """Mock config manager for testing."""
        return MagicMock(spec=ConfigManagerProtocol)

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        return MagicMock(spec=LoggerProtocol)

    @pytest.fixture
    def command_reference(self):
        """Create a sample command reference for testing."""
        commands = {
            "test-command": CommandInfo(
                name="test-command",
                description="A test command",
                category="test",
                parameters=[
                    ParameterInfo(
                        name="param1",
                        type_hint="str",
                        default_value="default",
                        description="A test parameter",
                        required=False,
                    )
                ],
            ),
            "other-command": CommandInfo(
                name="other-command",
                description="Another test command",
                category="general",
            ),
        }
        categories = {
            "test": ["test-command"],
            "general": ["other-command"],
        }
        workflows = {
            "test-workflow": ["test-command"],
        }
        return CommandReference(
            commands=commands,
            categories=categories,
            workflows=workflows,
        )

    def test_get_commands_by_category_returns_correct_commands(self, command_reference):
        """Test that get_commands_by_category returns commands for a specific category."""
        result = command_reference.get_commands_by_category("test")

        assert len(result) == 1
        assert result[0].name == "test-command"
        assert result[0].category == "test"

    def test_get_commands_by_category_returns_empty_list_for_unknown_category(self, command_reference):
        """Test that get_commands_by_category returns empty list for unknown category."""
        result = command_reference.get_commands_by_category("unknown")

        assert result == []

    def test_get_command_by_name_returns_command_by_name(self, command_reference):
        """Test that get_command_by_name returns command by its name."""
        result = command_reference.get_command_by_name("test-command")

        assert result is not None
        assert result.name == "test-command"
        assert result.description == "A test command"

    def test_get_command_by_name_returns_command_by_alias(self, command_reference):
        """Test that get_command_by_name returns command by its alias."""
        # Add an alias to test command
        command_reference.commands["test-command"].aliases = ["alias1", "alias2"]

        result = command_reference.get_command_by_name("alias1")

        assert result is not None
        assert result.name == "test-command"

    def test_get_command_by_name_returns_none_for_unknown_command(self, command_reference):
        """Test that get_command_by_name returns None for unknown command."""
        result = command_reference.get_command_by_name("unknown_command")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_reference_creates_reference(self, mock_config_manager, mock_logger):
        """Test that generate_reference creates a command reference."""
        generator = ReferenceGenerator(mock_config_manager, mock_logger)

        # Since this is an async method, we'll check if it can be awaited
        # We'll mock the internal method to avoid file system dependencies
        import asyncio
        from unittest.mock import AsyncMock

        # Mock the internal method to avoid file system dependencies
        generator._analyze_cli_module = AsyncMock(return_value={})
        generator._enhance_with_examples = AsyncMock(return_value={})
        generator._enhance_with_workflows = AsyncMock(return_value={})

        result = await generator.generate_reference("dummy_path")

        # The main assertion is that the method returns a CommandReference
        assert isinstance(result, CommandReference)

    @pytest.mark.asyncio
    async def test_render_reference_formats_correctly(self, mock_config_manager, mock_logger, command_reference):
        """Test that render_reference outputs in the correct format."""
        generator = ReferenceGenerator(mock_config_manager, mock_logger)

        # Test markdown rendering
        markdown_result = await generator.render_reference(command_reference, ReferenceFormat.MARKDOWN)
        assert isinstance(markdown_result, str)
        assert "# Command Reference" in markdown_result

        # Test JSON rendering
        json_result = await generator.render_reference(command_reference, ReferenceFormat.JSON)
        assert isinstance(json_result, str)
        assert '"commands": {' in json_result or '"commands":{}' in json_result


@pytest.mark.unit
class TestCommandInfo:
    """Unit tests for CommandInfo dataclass."""

    def test_command_info_initialization(self):
        """Test CommandInfo can be initialized with parameters."""
        param = ParameterInfo(
            name="test-param",
            type_hint="str",
            default_value="default_value",
            description="A test parameter",
            required=False,
        )

        command_info = CommandInfo(
            name="test-command",
            description="A test command",
            category="test",
            parameters=[param],
        )

        assert command_info.name == "test-command"
        assert command_info.description == "A test command"
        assert command_info.category == "test"
        assert len(command_info.parameters) == 1
        assert command_info.parameters[0].name == "test-param"

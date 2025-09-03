"""Unit tests for SessionPermissionsManager.

Tests the permission system that manages trusted operations
for the session management system.
"""

import tempfile
from pathlib import Path

import pytest
from session_mgmt_mcp.server import SessionPermissionsManager


class TestSessionPermissionsManager:
    """Test suite for SessionPermissionsManager."""

    @pytest.fixture
    def permissions_manager(self):
        """Create fresh SessionPermissionsManager instance."""
        claude_dir = Path(tempfile.mkdtemp())
        manager = SessionPermissionsManager(claude_dir)
        # Reset to clean state
        manager.trusted_operations.clear()
        return manager

    def test_singleton_pattern(self, permissions_manager):
        """Test that SessionPermissionsManager follows singleton pattern."""
        claude_dir = Path(tempfile.mkdtemp())
        manager1 = SessionPermissionsManager(claude_dir)
        manager2 = SessionPermissionsManager(claude_dir)

        assert manager1 is manager2

    def test_initial_state(self, permissions_manager):
        """Test initial state of permissions manager."""
        assert permissions_manager.trusted_operations == set()

    def test_trust_operation_success(self, permissions_manager):
        """Test successfully trusting an operation."""
        operation = "test_operation"

        permissions_manager.trust_operation(operation)

        assert operation in permissions_manager.trusted_operations

    def test_trust_operation_duplicate(self, permissions_manager):
        """Test trusting an already trusted operation."""
        operation = "test_operation"
        permissions_manager.trust_operation(operation)

        # Trust same operation again
        permissions_manager.trust_operation(operation)

        # Should not have duplicates
        assert len(permissions_manager.trusted_operations) == 1

    def test_trust_multiple_operations(self, permissions_manager):
        """Test trusting multiple operations."""
        operations = ["operation1", "operation2", "operation3"]

        for operation in operations:
            permissions_manager.trust_operation(operation)

        assert len(permissions_manager.trusted_operations) == len(operations)
        for operation in operations:
            assert operation in permissions_manager.trusted_operations

    def test_is_trusted_operation_positive(self, permissions_manager):
        """Test checking trusted operation returns True."""
        operation = "trusted_operation"
        permissions_manager.trust_operation(operation)

        assert permissions_manager.is_operation_trusted(operation) is True

    def test_is_trusted_operation_negative(self, permissions_manager):
        """Test checking untrusted operation returns False."""
        operation = "untrusted_operation"

        assert permissions_manager.is_operation_trusted(operation) is False

    def test_revoke_all_permissions(self, permissions_manager):
        """Test revoking all permissions."""
        # Trust several operations
        operations = ["op1", "op2", "op3"]
        for operation in operations:
            permissions_manager.trust_operation(operation)

        # Revoke all
        permissions_manager.revoke_all_permissions()

        assert permissions_manager.trusted_operations == set()

    def test_get_permission_status(self, permissions_manager):
        """Test getting permission status."""
        # Setup permissions
        permissions_manager.trust_operation("operation1")
        permissions_manager.trust_operation("operation2")

        status = permissions_manager.get_permission_status()

        assert status["trusted_operations_count"] == 2
        assert set(status["trusted_operations"]) == {"operation1", "operation2"}
        assert "session_id" in status
        assert "permissions_file" in status

    def test_edge_case_empty_operation_name(self, permissions_manager):
        """Test edge case with empty operation name."""
        permissions_manager.trust_operation("")

        assert "" in permissions_manager.trusted_operations

    def test_serialization_compatibility(self, permissions_manager):
        """Test that permissions manager state can be serialized."""
        # Setup some state
        permissions_manager.trust_operation("operation1")
        permissions_manager.trust_operation("operation2")

        # Get status (which should be JSON serializable)
        status = permissions_manager.get_permission_status()

        import json

        # Should be able to serialize
        serialized = json.dumps(status)
        assert "trusted_operations_count" in json.loads(serialized)

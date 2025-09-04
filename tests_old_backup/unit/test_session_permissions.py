"""Unit tests for SessionPermissionsManager.

Tests the permission system that manages trusted operations,
auto-checkpoints, and security controls for the session management system.
"""

from datetime import datetime, timedelta

import pytest
from session_mgmt_mcp.server import SessionPermissionsManager


class TestSessionPermissionsManager:
    """Test suite for SessionPermissionsManager."""

    @pytest.fixture
    def permissions_manager(self):
        """Create fresh SessionPermissionsManager instance."""
        manager = SessionPermissionsManager()
        # Reset to clean state
        manager.trusted_operations.clear()
        manager.auto_checkpoint = False
        manager.checkpoint_frequency = 300
        manager.last_checkpoint = None
        return manager

    def test_singleton_pattern(self):
        """Test that SessionPermissionsManager follows singleton pattern."""
        manager1 = SessionPermissionsManager()
        manager2 = SessionPermissionsManager()

        assert manager1 is manager2

    def test_initial_state(self, permissions_manager):
        """Test initial state of permissions manager."""
        assert permissions_manager.trusted_operations == set()
        assert permissions_manager.auto_checkpoint is False
        assert permissions_manager.checkpoint_frequency == 300
        assert permissions_manager.last_checkpoint is None

    def test_trust_operation_success(self, permissions_manager):
        """Test successfully trusting an operation."""
        operation = "test_operation"

        result = permissions_manager.trust_operation(operation)

        assert result is True
        assert operation in permissions_manager.trusted_operations

    def test_trust_operation_duplicate(self, permissions_manager):
        """Test trusting an already trusted operation."""
        operation = "test_operation"
        permissions_manager.trust_operation(operation)

        # Trust same operation again
        result = permissions_manager.trust_operation(operation)

        assert result is True
        assert operation in permissions_manager.trusted_operations
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

        assert permissions_manager.is_trusted_operation(operation) is True

    def test_is_trusted_operation_negative(self, permissions_manager):
        """Test checking untrusted operation returns False."""
        operation = "untrusted_operation"

        assert permissions_manager.is_trusted_operation(operation) is False

    def test_revoke_all_permissions(self, permissions_manager):
        """Test revoking all permissions."""
        # Trust several operations
        operations = ["op1", "op2", "op3"]
        for operation in operations:
            permissions_manager.trust_operation(operation)

        # Enable auto-checkpoint
        permissions_manager.auto_checkpoint = True

        # Revoke all
        permissions_manager.revoke_all_permissions()

        assert permissions_manager.trusted_operations == set()
        assert permissions_manager.auto_checkpoint is False

    def test_configure_auto_checkpoint_enable(self, permissions_manager):
        """Test enabling auto-checkpoint."""
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=600,
        )

        assert result is True
        assert permissions_manager.auto_checkpoint is True
        assert permissions_manager.checkpoint_frequency == 600

    def test_configure_auto_checkpoint_disable(self, permissions_manager):
        """Test disabling auto-checkpoint."""
        # First enable it
        permissions_manager.configure_auto_checkpoint(enabled=True, frequency=300)

        # Then disable
        result = permissions_manager.configure_auto_checkpoint(enabled=False)

        assert result is True
        assert permissions_manager.auto_checkpoint is False
        # Frequency should remain unchanged
        assert permissions_manager.checkpoint_frequency == 300

    def test_configure_auto_checkpoint_invalid_frequency(self, permissions_manager):
        """Test configuring auto-checkpoint with invalid frequency."""
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=-100,
        )

        assert result is False
        assert permissions_manager.auto_checkpoint is False

    def test_should_auto_checkpoint_disabled(self, permissions_manager):
        """Test auto-checkpoint check when disabled."""
        permissions_manager.auto_checkpoint = False

        assert permissions_manager.should_auto_checkpoint() is False

    def test_should_auto_checkpoint_no_previous(self, permissions_manager):
        """Test auto-checkpoint check with no previous checkpoint."""
        permissions_manager.auto_checkpoint = True
        permissions_manager.checkpoint_frequency = 300

        # Should checkpoint immediately if never done before
        assert permissions_manager.should_auto_checkpoint() is True

    def test_should_auto_checkpoint_recent(self, permissions_manager):
        """Test auto-checkpoint check with recent checkpoint."""
        permissions_manager.auto_checkpoint = True
        permissions_manager.checkpoint_frequency = 300
        permissions_manager.last_checkpoint = datetime.now()

        assert permissions_manager.should_auto_checkpoint() is False

    def test_should_auto_checkpoint_overdue(self, permissions_manager):
        """Test auto-checkpoint check with overdue checkpoint."""
        permissions_manager.auto_checkpoint = True
        permissions_manager.checkpoint_frequency = 300  # 5 minutes
        # Set last checkpoint to 10 minutes ago
        permissions_manager.last_checkpoint = datetime.now() - timedelta(minutes=10)

        assert permissions_manager.should_auto_checkpoint() is True

    def test_record_checkpoint(self, permissions_manager):
        """Test recording checkpoint timestamp."""
        before_time = datetime.now()

        permissions_manager.record_checkpoint()

        after_time = datetime.now()

        assert permissions_manager.last_checkpoint is not None
        assert before_time <= permissions_manager.last_checkpoint <= after_time

    def test_get_permissions_summary_empty(self, permissions_manager):
        """Test permissions summary with no permissions."""
        summary = permissions_manager.get_permissions_summary()

        expected = {
            "trusted_operations_count": 0,
            "trusted_operations": [],
            "auto_checkpoint_enabled": False,
            "checkpoint_frequency_minutes": 5.0,
            "last_checkpoint": None,
            "should_checkpoint": False,
        }

        assert summary == expected

    def test_get_permissions_summary_with_data(self, permissions_manager):
        """Test permissions summary with data."""
        # Setup permissions
        permissions_manager.trust_operation("operation1")
        permissions_manager.trust_operation("operation2")
        permissions_manager.configure_auto_checkpoint(enabled=True, frequency=600)
        checkpoint_time = datetime.now()
        permissions_manager.last_checkpoint = checkpoint_time

        summary = permissions_manager.get_permissions_summary()

        assert summary["trusted_operations_count"] == 2
        assert set(summary["trusted_operations"]) == {"operation1", "operation2"}
        assert summary["auto_checkpoint_enabled"] is True
        assert summary["checkpoint_frequency_minutes"] == 10.0
        assert summary["last_checkpoint"] == checkpoint_time.isoformat()
        assert summary["should_checkpoint"] is False  # Recent checkpoint

    @pytest.mark.parametrize(
        ("frequency", "expected_minutes"),
        [(60, 1.0), (300, 5.0), (600, 10.0), (1800, 30.0), (3600, 60.0)],
    )
    def test_checkpoint_frequency_conversion(
        self,
        permissions_manager,
        frequency,
        expected_minutes,
    ):
        """Test checkpoint frequency conversion to minutes."""
        permissions_manager.checkpoint_frequency = frequency
        summary = permissions_manager.get_permissions_summary()

        assert summary["checkpoint_frequency_minutes"] == expected_minutes

    def test_concurrent_access_thread_safety(self, permissions_manager):
        """Test thread safety of concurrent access."""
        import threading
        import time

        results = []
        errors = []

        def trust_operations(start_index, count) -> None:
            try:
                for i in range(start_index, start_index + count):
                    operation = f"operation_{i}"
                    result = permissions_manager.trust_operation(operation)
                    results.append((operation, result))
                    time.sleep(
                        0.001,
                    )  # Small delay to increase chance of race condition
            except Exception as e:
                errors.append(e)

        # Create multiple threads trusting operations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=trust_operations, args=(i * 10, 10))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 50  # 5 threads * 10 operations each
        assert len(permissions_manager.trusted_operations) == 50

    def test_edge_case_empty_operation_name(self, permissions_manager):
        """Test edge case with empty operation name."""
        result = permissions_manager.trust_operation("")

        assert result is True
        assert "" in permissions_manager.trusted_operations

    def test_edge_case_whitespace_operation_name(self, permissions_manager):
        """Test edge case with whitespace operation name."""
        operation = "   whitespace_operation   "
        result = permissions_manager.trust_operation(operation)

        assert result is True
        assert operation in permissions_manager.trusted_operations

    def test_edge_case_none_operation_name(self, permissions_manager):
        """Test edge case with None operation name."""
        with pytest.raises(TypeError):
            permissions_manager.trust_operation(None)

    def test_checkpoint_frequency_boundary_values(self, permissions_manager):
        """Test checkpoint frequency with boundary values."""
        # Test minimum valid value
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=1,
        )
        assert result is True
        assert permissions_manager.checkpoint_frequency == 1

        # Test zero (invalid)
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=0,
        )
        assert result is False

        # Test large value
        result = permissions_manager.configure_auto_checkpoint(
            enabled=True,
            frequency=86400,  # 24 hours
        )
        assert result is True
        assert permissions_manager.checkpoint_frequency == 86400

    def test_memory_usage_with_many_operations(self, permissions_manager):
        """Test memory usage with many trusted operations."""
        import sys

        # Get initial size
        initial_size = sys.getsizeof(permissions_manager.trusted_operations)

        # Add many operations
        for i in range(1000):
            permissions_manager.trust_operation(f"operation_{i}")

        # Check final size
        final_size = sys.getsizeof(permissions_manager.trusted_operations)

        # Ensure reasonable memory growth
        assert final_size > initial_size
        assert final_size < initial_size * 100  # Shouldn't grow excessively
        assert len(permissions_manager.trusted_operations) == 1000

    def test_serialization_compatibility(self, permissions_manager):
        """Test that permissions manager state can be serialized."""
        # Setup some state
        permissions_manager.trust_operation("operation1")
        permissions_manager.trust_operation("operation2")
        permissions_manager.configure_auto_checkpoint(enabled=True, frequency=600)

        # Get summary (which should be JSON serializable)
        summary = permissions_manager.get_permissions_summary()

        import json

        # Should be able to serialize and deserialize
        serialized = json.dumps(summary)
        deserialized = json.loads(serialized)

        assert deserialized["trusted_operations_count"] == 2
        assert set(deserialized["trusted_operations"]) == {"operation1", "operation2"}
        assert deserialized["auto_checkpoint_enabled"] is True

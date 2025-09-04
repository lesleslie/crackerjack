#!/usr/bin/env python3
"""Example unit tests showing how to use the test infrastructure."""

from tests.helpers import AssertionHelper, MockingHelper, TestDataFactory


class TestExampleUnit:
    """Example unit tests for individual components."""

    def test_data_factory_basic_usage(self):
        """Example of using TestDataFactory for unit tests."""
        # Generate test data
        conversation = TestDataFactory.conversation(
            content="Unit test conversation", project="unit-test-project"
        )

        # Validate structure
        AssertionHelper.assert_database_record(
            conversation, ["id", "content", "project", "timestamp"]
        )

        assert conversation["content"] == "Unit test conversation"
        assert conversation["project"] == "unit-test-project"

    def test_mock_embedding_system(self):
        """Example of testing with mocked embedding system."""
        embedding_mocks = MockingHelper.mock_embedding_system()

        # Test the mock system directly
        assert embedding_mocks["onnx_session"] is not None
        assert embedding_mocks["tokenizer"] is not None

        # Test ONNX mock returns expected format
        onnx_result = embedding_mocks["onnx_session"].run.return_value
        assert len(onnx_result) == 1
        assert onnx_result[0].shape == (1, 384)

        # Test tokenizer mock returns expected format
        tokenizer_result = embedding_mocks["tokenizer"].return_value
        assert "input_ids" in tokenizer_result
        assert "attention_mask" in tokenizer_result

    def test_assertion_helpers_validation(self):
        """Example of using assertion helpers."""
        import uuid
        from datetime import UTC, datetime

        import numpy as np

        # Test UUID validation
        test_uuid = str(uuid.uuid4())
        AssertionHelper.assert_valid_uuid(test_uuid)

        # Test timestamp validation
        test_timestamp = datetime.now(UTC).isoformat()
        AssertionHelper.assert_valid_timestamp(test_timestamp)

        # Test embedding shape validation
        rng = np.random.default_rng(42)
        test_embedding = rng.random((384,)).astype(np.float32)
        AssertionHelper.assert_embedding_shape(test_embedding)

        # Test similarity score validation
        AssertionHelper.assert_similarity_score(0.85)

    def test_mock_environment_variables(self):
        """Example of testing with environment variable mocking."""
        test_env = {"TEST_VAR": "test_value", "LOG_LEVEL": "DEBUG"}

        with MockingHelper.patch_environment(**test_env):
            import os

            assert os.environ.get("TEST_VAR") == "test_value"
            assert os.environ.get("LOG_LEVEL") == "DEBUG"

    def test_bulk_data_generation(self):
        """Example of generating bulk test data for unit tests."""
        # Generate multiple conversations
        conversations = TestDataFactory.bulk_conversations(10, "bulk-test-project")

        assert len(conversations) == 10
        assert all(conv["project"] == "bulk-test-project" for conv in conversations)

        # Validate each conversation
        for conv in conversations:
            AssertionHelper.assert_valid_uuid(conv["id"])
            assert conv["content"].startswith("Bulk conversation")

    def test_with_custom_marker(self):
        """Example test with custom marker."""
        # This test will be categorized as a unit test
        assert True  # Simple assertion for example

#!/usr/bin/env python3
"""Test suite for automatic compaction functionality in session-mgmt-mcp.

Tests the enhanced checkpoint workflow that automatically handles context compaction.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_mgmt_mcp.reflection_tools import get_reflection_database
from session_mgmt_mcp.server import (
    analyze_token_usage_patterns,
    capture_session_insights,
    perform_strategic_compaction,
    summarize_current_conversation,
)


class TestAutoCompaction:
    """Test suite for automatic compaction functionality."""

    @pytest.mark.asyncio
    async def test_token_analysis_recommends_compaction(self):
        """Test that token analysis always recommends compaction during checkpoints."""
        result = await analyze_token_usage_patterns()

        # Should always recommend compaction (we modified the logic)
        assert result["recommend_compact"], "Token analysis should recommend compaction"
        assert result["needs_attention"], "Token analysis should flag attention needed"
        assert result["status"] == "needs optimization", (
            "Status should indicate optimization needed"
        )

    @pytest.mark.asyncio
    async def test_strategic_compaction_includes_conversation(self):
        """Test that strategic compaction includes conversation compaction."""
        results = await perform_strategic_compaction()

        # Check for conversation compaction indicators
        result_text = " ".join(results).lower()

        assert "conversation compaction" in result_text, (
            "Should include conversation compaction section"
        )
        assert "context summary stored" in result_text, "Should store context summary"
        assert "should be compacted" in result_text, "Should recommend compaction"

    @pytest.mark.asyncio
    async def test_conversation_summarization(self):
        """Test that conversation summarization works correctly."""
        summary = await summarize_current_conversation()

        # Should contain key components
        assert "key_topics" in summary, "Summary should have key_topics"
        assert "decisions_made" in summary, "Summary should have decisions_made"
        assert "next_steps" in summary, "Summary should have next_steps"

        # Should have content (even if fallback)
        assert len(summary["key_topics"]) > 0, "Should have at least one topic"
        assert len(summary["decisions_made"]) > 0, "Should have at least one decision"

    @pytest.mark.asyncio
    async def test_context_preservation_in_database(self):
        """Test that context is preserved in reflection database."""
        try:
            db = await get_reflection_database()

            # Store a test context summary
            test_summary = "Test context preservation for auto-compaction functionality"
            reflection_id = await db.store_reflection(
                test_summary,
                ["test", "auto-compact", "context-preservation"],
            )

            assert reflection_id, "Should return reflection ID"
            assert len(reflection_id) > 0, "Reflection ID should not be empty"

            # Verify we can search for it
            results = await db.search_reflections("context preservation", limit=1)
            assert len(results) > 0, "Should be able to find stored context"

        except ImportError:
            pytest.skip("Reflection database not available")

    @pytest.mark.asyncio
    async def test_enhanced_session_insights(self):
        """Test that enhanced session insights include conversation data."""
        results = await capture_session_insights(90.0)

        # Should have multiple types of insights stored
        stored_insights = [r for r in results if "stored:" in r.lower()]
        assert len(stored_insights) > 1, "Should store multiple types of insights"

        # Should include conversation topics
        result_text = " ".join(results).lower()
        assert any(
            keyword in result_text for keyword in ["topics", "decisions", "next steps"]
        ), "Should include conversation elements"


class TestCompactionWorkflow:
    """Test the complete compaction workflow."""

    @pytest.mark.asyncio
    async def test_compaction_recommendation_flow(self):
        """Test the complete flow from detection to recommendation."""
        # Step 1: Token analysis should detect need for compaction
        token_result = await analyze_token_usage_patterns()
        assert token_result["recommend_compact"], "Step 1: Should recommend compaction"

        # Step 2: Strategic compaction should prepare for compaction
        compaction_results = await perform_strategic_compaction()
        compaction_text = " ".join(compaction_results).lower()
        assert "conversation compaction" in compaction_text, (
            "Step 2: Should prepare conversation compaction"
        )

        # Step 3: Conversation summary should be generated
        summary = await summarize_current_conversation()
        assert len(summary["key_topics"]) > 0, (
            "Step 3: Should generate conversation summary"
        )

        print("✅ Complete compaction workflow tested successfully")

    @pytest.mark.asyncio
    async def test_checkpoint_integration(self):
        """Test that all components integrate properly in checkpoint."""
        # Test individual components work
        token_analysis = await analyze_token_usage_patterns()
        conversation_summary = await summarize_current_conversation()
        strategic_compaction = await perform_strategic_compaction()

        # Verify integration points
        assert token_analysis["recommend_compact"], (
            "Token analysis should trigger compaction"
        )
        assert len(conversation_summary["key_topics"]) > 0, (
            "Conversation summary should have content"
        )

        compaction_text = " ".join(strategic_compaction).lower()
        assert "compaction" in compaction_text, (
            "Strategic compaction should handle compaction"
        )

        print("✅ Checkpoint integration verified")


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(TestAutoCompaction().test_token_analysis_recommends_compaction())
    asyncio.run(TestAutoCompaction().test_strategic_compaction_includes_conversation())
    asyncio.run(TestAutoCompaction().test_conversation_summarization())
    asyncio.run(TestAutoCompaction().test_context_preservation_in_database())
    asyncio.run(TestAutoCompaction().test_enhanced_session_insights())

    asyncio.run(TestCompactionWorkflow().test_compaction_recommendation_flow())
    asyncio.run(TestCompactionWorkflow().test_checkpoint_integration())

    print("\n🎉 All auto-compaction tests passed!")

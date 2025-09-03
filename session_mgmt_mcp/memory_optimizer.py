#!/usr/bin/env python3
"""Memory Optimization for Session Management MCP Server.

Provides conversation consolidation, summarization, and memory compression capabilities.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

from .reflection_tools import ReflectionDatabase


class ConversationSummarizer:
    """Handles conversation summarization using various strategies."""

    def __init__(self) -> None:
        self.summarization_strategies = {
            "extractive": self._extractive_summarization,
            "template_based": self._template_based_summarization,
            "keyword_based": self._keyword_based_summarization,
        }

    def _extractive_summarization(self, content: str, max_sentences: int = 3) -> str:
        """Extract most important sentences from conversation."""
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Score sentences based on various factors
        scored_sentences = []
        for sentence in sentences[:20]:  # Limit to prevent performance issues
            score = 0

            # Length score (prefer medium-length sentences)
            length = len(sentence.split())
            if 10 <= length <= 30:
                score += 0.3

            # Technical keywords score
            tech_keywords = [
                "function",
                "class",
                "error",
                "exception",
                "import",
                "def",
                "async",
                "await",
                "return",
                "variable",
                "method",
                "api",
                "database",
                "query",
                "test",
                "debug",
                "fix",
                "implement",
            ]
            for keyword in tech_keywords:
                if keyword.lower() in sentence.lower():
                    score += 0.1

            # Code presence score
            if "`" in sentence or "def " in sentence or "class " in sentence:
                score += 0.2

            # Question/problem indicators
            question_words = ["how", "why", "what", "when", "where", "which"]
            if any(word in sentence.lower() for word in question_words):
                score += 0.15

            # Solution indicators
            solution_words = ["solution", "fix", "resolve", "implement", "create"]
            if any(word in sentence.lower() for word in solution_words):
                score += 0.2

            scored_sentences.append((score, sentence))

        # Sort by score and take top sentences
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentences = [sent for score, sent in scored_sentences[:max_sentences]]

        return ". ".join(top_sentences) + "."

    def _template_based_summarization(self, content: str, max_length: int = 300) -> str:
        """Create summary using templates based on content patterns."""
        summary_parts = []

        # Detect code blocks
        code_blocks = re.findall(r"```[\w]*\n(.*?)\n```", content, re.DOTALL)
        if code_blocks:
            summary_parts.append(
                f"Code discussion involving {len(code_blocks)} code block(s)",
            )

        # Detect errors/exceptions
        error_patterns = [
            r"(\w+Error): (.+)",
            r"Exception: (.+)",
            r"Traceback \(most recent call last\):",
            r"error: (.+)",
        ]
        errors_found = []
        for pattern in error_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    errors_found.extend([match[0] for match in matches[:2]])
                else:
                    errors_found.extend(matches[:2])

        if errors_found:
            error_summary = ", ".join(set(errors_found))[:100]
            summary_parts.append(f"Error troubleshooting: {error_summary}")

        # Detect file/project references
        file_patterns = [
            r"(\w+\.py)",
            r"(\w+\.js)",
            r"(\w+\.ts)",
            r"(\w+\.json)",
            r"(\w+\.md)",
        ]
        files_mentioned = set()
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            files_mentioned.update(matches[:5])  # Limit to 5 files

        if files_mentioned:
            files_str = ", ".join(sorted(files_mentioned))
            summary_parts.append(f"Files discussed: {files_str}")

        # Detect implementation topics
        impl_keywords = {
            "function": "function implementation",
            "class": "class design",
            "api": "API development",
            "database": "database operations",
            "test": "testing strategies",
            "deploy": "deployment process",
            "refactor": "code refactoring",
            "optimization": "performance optimization",
        }

        topics_found = []
        for keyword, topic in impl_keywords.items():
            if keyword in content.lower():
                topics_found.append(topic)

        if topics_found:
            topics_str = ", ".join(topics_found[:3])
            summary_parts.append(f"Topics: {topics_str}")

        # Combine parts and ensure length limit
        full_summary = "; ".join(summary_parts)
        if len(full_summary) > max_length:
            full_summary = full_summary[:max_length] + "..."

        return full_summary or "General development discussion"

    def _keyword_based_summarization(self, content: str, max_keywords: int = 10) -> str:
        """Create summary based on extracted keywords."""
        # Clean content
        content_clean = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        content_clean = re.sub(r"`[^`]+`", "", content_clean)

        # Extract potential keywords
        words = re.findall(r"\b[a-zA-Z]{3,}\b", content_clean.lower())

        # Filter common words
        stop_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "day",
            "get",
            "has",
            "him",
            "his",
            "how",
            "its",
            "may",
            "new",
            "now",
            "old",
            "see",
            "two",
            "who",
            "boy",
            "did",
            "way",
            "use",
            "man",
            "say",
            "she",
            "too",
            "any",
            "here",
            "much",
            "where",
            "your",
            "them",
            "well",
            "were",
            "been",
            "have",
            "there",
            "what",
            "would",
            "make",
            "like",
            "into",
            "time",
            "will",
            "about",
            "think",
            "never",
            "after",
            "should",
            "could",
            "also",
            "just",
            "first",
            "over",
            "back",
            "other",
        }

        # Count word frequencies
        word_counts = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1

        # Get top keywords
        top_keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, count in top_keywords[:max_keywords]]

        return f"Keywords: {', '.join(keywords)}" if keywords else "General discussion"

    def summarize_conversation(
        self,
        content: str,
        strategy: str = "template_based",
    ) -> str:
        """Summarize a conversation using the specified strategy."""
        if strategy not in self.summarization_strategies:
            strategy = "template_based"

        try:
            summary = self.summarization_strategies[strategy](content)
            return summary or "Unable to generate summary"
        except Exception as e:
            return f"Summary generation failed: {str(e)[:100]}"


class ConversationClusterer:
    """Groups related conversations for consolidation."""

    def __init__(self) -> None:
        self.similarity_threshold = 0.6

    def cluster_conversations(
        self,
        conversations: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """Group conversations into clusters based on similarity."""
        if not conversations:
            return []

        clusters = []
        used_conversations = set()

        for i, conv in enumerate(conversations):
            if i in used_conversations:
                continue

            # Start new cluster
            cluster = [conv]
            used_conversations.add(i)

            # Find similar conversations
            for j, other_conv in enumerate(conversations[i + 1 :], i + 1):
                if j in used_conversations:
                    continue

                similarity = self._calculate_similarity(conv, other_conv)
                if similarity >= self.similarity_threshold:
                    cluster.append(other_conv)
                    used_conversations.add(j)

            clusters.append(cluster)

        return clusters

    def _calculate_similarity(
        self,
        conv1: dict[str, Any],
        conv2: dict[str, Any],
    ) -> float:
        """Calculate similarity between two conversations."""
        similarity = 0.0

        # Project similarity
        if conv1.get("project") == conv2.get("project"):
            similarity += 0.3

        # Time proximity (conversations within same day)
        try:
            time1 = datetime.fromisoformat(conv1.get("timestamp", ""))
            time2 = datetime.fromisoformat(conv2.get("timestamp", ""))
            if abs((time1 - time2).days) <= 1:
                similarity += 0.2
        except (ValueError, TypeError):
            pass

        # Content similarity (simple keyword overlap)
        content1_words = set(re.findall(r"\b\w+\b", conv1.get("content", "").lower()))
        content2_words = set(re.findall(r"\b\w+\b", conv2.get("content", "").lower()))

        if content1_words and content2_words:
            overlap = len(content1_words & content2_words)
            total = len(content1_words | content2_words)
            if total > 0:
                similarity += 0.5 * (overlap / total)

        return min(similarity, 1.0)


class RetentionPolicyManager:
    """Manages conversation retention policies."""

    def __init__(self) -> None:
        self.default_policies = {
            "max_age_days": 365,  # Keep conversations for 1 year
            "max_conversations": 10000,  # Maximum number of conversations
            "importance_threshold": 0.3,  # Minimum importance score to keep
            "consolidation_age_days": 30,  # Consolidate conversations older than 30 days
            "compression_ratio": 0.5,  # Target 50% size reduction when consolidating
        }

        self.importance_factors = {
            "has_code": 0.3,
            "has_errors": 0.2,
            "recent_access": 0.2,
            "length_score": 0.1,
            "project_relevance": 0.2,
        }

    def calculate_importance_score(self, conversation: dict[str, Any]) -> float:
        """Calculate importance score for a conversation."""
        score = 0.0
        content = conversation.get("content", "")

        # Has code blocks
        if "```" in content or "def " in content or "class " in content:
            score += self.importance_factors["has_code"]

        # Has error/exception information
        error_keywords = ["error", "exception", "traceback", "failed", "bug"]
        if any(keyword in content.lower() for keyword in error_keywords):
            score += self.importance_factors["has_errors"]

        # Recent access (would need to track this separately)
        # For now, use recency as proxy
        try:
            conv_time = datetime.fromisoformat(conversation.get("timestamp", ""))
            days_old = (datetime.now() - conv_time).days
            if days_old < 7:
                score += self.importance_factors["recent_access"]
            elif days_old < 30:
                score += self.importance_factors["recent_access"] * 0.5
        except (ValueError, TypeError):
            pass

        # Length score (longer conversations might be more important)
        content_length = len(content)
        if content_length > 1000:
            score += self.importance_factors["length_score"]
        elif content_length > 500:
            score += self.importance_factors["length_score"] * 0.5

        # Project relevance (current project gets boost)
        # This would need current project context
        score += (
            self.importance_factors["project_relevance"] * 0.5
        )  # Default middle score

        return min(score, 1.0)

    def get_conversations_for_retention(
        self,
        conversations: list[dict[str, Any]],
        policy: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Determine which conversations to keep vs consolidate/delete."""
        if not policy:
            policy = self.default_policies.copy()

        keep_conversations = []
        consolidate_conversations = []

        # Sort conversations by timestamp (newest first)
        sorted_conversations = sorted(
            conversations,
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )

        cutoff_date = datetime.now() - timedelta(days=policy["consolidation_age_days"])
        max_conversations = policy["max_conversations"]
        importance_threshold = policy["importance_threshold"]

        for i, conv in enumerate(sorted_conversations):
            # Always keep recent conversations up to max limit
            if i < max_conversations // 2:  # Keep newest 50% of max limit
                keep_conversations.append(conv)
                continue

            # Check importance for older conversations
            importance = self.calculate_importance_score(conv)
            conv["importance_score"] = importance

            # Check age
            try:
                conv_time = datetime.fromisoformat(conv.get("timestamp", ""))
                is_old = conv_time < cutoff_date
            except (ValueError, TypeError):
                is_old = True  # If we can't parse timestamp, consider it old

            if importance >= importance_threshold:
                keep_conversations.append(conv)
            elif is_old:
                consolidate_conversations.append(conv)
            else:
                # Recent but low importance - keep for now
                keep_conversations.append(conv)

        return keep_conversations, consolidate_conversations


class MemoryOptimizer:
    """Main class for memory optimization and compression."""

    def __init__(self, reflection_db: ReflectionDatabase) -> None:
        self.reflection_db = reflection_db
        self.summarizer = ConversationSummarizer()
        self.clusterer = ConversationClusterer()
        self.retention_manager = RetentionPolicyManager()

        # Compression statistics
        self.compression_stats = {
            "last_run": None,
            "conversations_processed": 0,
            "conversations_consolidated": 0,
            "space_saved_bytes": 0,
            "compression_ratio": 0.0,
        }

    async def compress_memory(
        self,
        policy: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Main method to compress conversation memory."""
        if not hasattr(self.reflection_db, "conn") or not self.reflection_db.conn:
            return {"error": "Database not available"}

        # Get all conversations
        cursor = self.reflection_db.conn.execute(
            "SELECT id, content, project, timestamp, metadata FROM conversations ORDER BY timestamp DESC",
        )
        conversations = []
        for row in cursor.fetchall():
            conv_id, content, project, timestamp, metadata = row
            conversations.append(
                {
                    "id": conv_id,
                    "content": content,
                    "project": project,
                    "timestamp": timestamp,
                    "metadata": json.loads(metadata) if metadata else {},
                    "original_size": len(content),
                },
            )

        if not conversations:
            return {
                "status": "no_conversations",
                "message": "No conversations found to compress",
            }

        # Apply retention policy
        keep_conversations, consolidate_conversations = (
            self.retention_manager.get_conversations_for_retention(
                conversations,
                policy,
            )
        )

        # Cluster conversations for consolidation
        clusters = self.clusterer.cluster_conversations(consolidate_conversations)

        results = {
            "status": "success",
            "dry_run": dry_run,
            "total_conversations": len(conversations),
            "conversations_to_keep": len(keep_conversations),
            "conversations_to_consolidate": len(consolidate_conversations),
            "clusters_created": len(clusters),
            "consolidated_summaries": [],
            "space_saved_estimate": 0,
            "compression_ratio": 0.0,
        }

        # Process clusters
        total_original_size = sum(
            conv["original_size"] for conv in consolidate_conversations
        )
        total_compressed_size = 0

        for _i, cluster in enumerate(clusters):
            if len(cluster) <= 1:
                continue  # Skip single-conversation clusters

            # Create consolidated summary
            combined_content = "\n\n---\n\n".join([conv["content"] for conv in cluster])
            summary = self.summarizer.summarize_conversation(
                combined_content,
                "template_based",
            )

            # Create consolidated metadata
            projects = list(
                {conv["project"] for conv in cluster if conv["project"]},
            )
            timestamps = [conv["timestamp"] for conv in cluster]
            min_time = min(timestamps) if timestamps else ""
            max_time = max(timestamps) if timestamps else ""

            consolidated_conv = {
                "summary": summary,
                "original_count": len(cluster),
                "projects": projects,
                "time_range": f"{min_time} to {max_time}",
                "original_conversations": [conv["id"] for conv in cluster],
                "compressed_size": len(summary),
                "original_size": sum(conv["original_size"] for conv in cluster),
            }

            total_compressed_size += len(summary)
            results["consolidated_summaries"].append(consolidated_conv)

            # Actually perform consolidation if not dry run
            if not dry_run:
                await self._create_consolidated_conversation(consolidated_conv, cluster)

        # Calculate compression statistics
        if total_original_size > 0:
            space_saved = total_original_size - total_compressed_size
            compression_ratio = space_saved / total_original_size
            results["space_saved_estimate"] = space_saved
            results["compression_ratio"] = compression_ratio

        # Update compression stats
        self.compression_stats.update(
            {
                "last_run": datetime.now().isoformat(),
                "conversations_processed": len(consolidate_conversations),
                "conversations_consolidated": sum(
                    len(cluster) for cluster in clusters if len(cluster) > 1
                ),
                "space_saved_bytes": results["space_saved_estimate"],
                "compression_ratio": results["compression_ratio"],
            },
        )

        return results

    async def _create_consolidated_conversation(
        self,
        consolidated_conv: dict[str, Any],
        original_cluster: list[dict[str, Any]],
    ) -> None:
        """Create a new consolidated conversation and remove originals."""
        # Create new consolidated conversation
        consolidated_id = hashlib.md5(
            f"consolidated_{datetime.now().isoformat()}".encode(),
        ).hexdigest()

        metadata = {
            "type": "consolidated",
            "original_count": consolidated_conv["original_count"],
            "original_conversations": consolidated_conv["original_conversations"],
            "projects": consolidated_conv["projects"],
            "compression_ratio": consolidated_conv["compressed_size"]
            / consolidated_conv["original_size"],
        }

        # Insert consolidated conversation
        self.reflection_db.conn.execute(
            """INSERT INTO conversations (id, content, project, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (
                consolidated_id,
                consolidated_conv["summary"],
                ", ".join(consolidated_conv["projects"])
                if consolidated_conv["projects"]
                else "multiple",
                datetime.now().isoformat(),
                json.dumps(metadata),
            ),
        )

        # Remove original conversations
        original_ids = [conv["id"] for conv in original_cluster]
        if original_ids:
            placeholders = ",".join(["?" for _ in original_ids])
            self.reflection_db.conn.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                original_ids,
            )

        # Commit changes
        self.reflection_db.conn.commit()

    async def get_compression_stats(self) -> dict[str, Any]:
        """Get compression statistics."""
        return self.compression_stats.copy()

    async def set_retention_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        """Update retention policy settings."""
        updated_policy = self.retention_manager.default_policies.copy()
        updated_policy.update(policy)

        # Validate policy values
        if updated_policy.get("max_age_days", 0) < 1:
            return {"error": "max_age_days must be at least 1"}

        if updated_policy.get("max_conversations", 0) < 100:
            return {"error": "max_conversations must be at least 100"}

        self.retention_manager.default_policies = updated_policy

        return {"status": "success", "updated_policy": updated_policy}

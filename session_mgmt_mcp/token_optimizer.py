#!/usr/bin/env python3
"""Token Optimization for Session Management MCP Server.

Provides response chunking, content truncation, and context window monitoring
to reduce token usage while maintaining functionality.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import tiktoken


@dataclass
class TokenUsageMetrics:
    """Token usage metrics for monitoring."""

    request_tokens: int
    response_tokens: int
    total_tokens: int
    timestamp: str
    operation: str
    optimization_applied: str | None = None


@dataclass
class ChunkResult:
    """Result of response chunking."""

    chunks: list[str]
    total_chunks: int
    current_chunk: int
    cache_key: str
    metadata: dict[str, Any]


class TokenOptimizer:
    """Main token optimization class."""

    def __init__(self, max_tokens: int = 4000, chunk_size: int = 2000) -> None:
        self.max_tokens = max_tokens
        self.chunk_size = chunk_size
        self.encoding = self._get_encoding()
        self.usage_history: list[TokenUsageMetrics] = []
        self.chunk_cache: dict[str, ChunkResult] = {}

        # Token optimization strategies
        self.strategies = {
            "truncate_old": self._truncate_old_conversations,
            "summarize_content": self._summarize_long_content,
            "chunk_response": self._chunk_large_response,
            "filter_duplicates": self._filter_duplicate_content,
            "prioritize_recent": self._prioritize_recent_content,
        }

    def _get_encoding(self):
        """Get tiktoken encoding for token counting."""
        try:
            return tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        except Exception:
            # Fallback to approximate counting
            return None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.encoding:
            return len(self.encoding.encode(text))
        # Rough approximation: ~4 chars per token
        return len(text) // 4

    def optimize_search_results(
        self,
        results: list[dict[str, Any]],
        strategy: str = "truncate_old",
        max_tokens: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Optimize search results to reduce token usage."""
        max_tokens = max_tokens or self.max_tokens

        if strategy in self.strategies:
            optimized_results, optimization_info = self.strategies[strategy](
                results,
                max_tokens,
            )
        else:
            optimized_results, optimization_info = results, {"strategy": "none"}

        # Track optimization metrics
        optimization_info["original_count"] = len(results)
        optimization_info["optimized_count"] = len(optimized_results)
        optimization_info["token_savings"] = self._calculate_token_savings(
            results,
            optimized_results,
        )

        return optimized_results, optimization_info

    def _truncate_old_conversations(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Truncate old conversations based on age and importance."""
        if not results:
            return results, {"strategy": "truncate_old", "action": "no_results"}

        # Sort by timestamp (newest first)
        sorted_results = sorted(
            results,
            key=lambda x: x.get("timestamp", ""),
            reverse=True,
        )

        optimized_results = []
        current_tokens = 0
        truncation_count = 0

        for result in sorted_results:
            content = result.get("content", "")
            content_tokens = self.count_tokens(content)

            # Check if adding this result exceeds token limit
            if current_tokens + content_tokens > max_tokens:
                # Try truncating the content
                if len(optimized_results) < 3:  # Always keep at least 3 recent results
                    truncated_content = self._truncate_content(
                        content,
                        max_tokens - current_tokens,
                    )
                    if truncated_content:
                        result_copy = result.copy()
                        result_copy["content"] = (
                            truncated_content + "... [truncated for token limit]"
                        )
                        optimized_results.append(result_copy)
                        truncation_count += 1
                        break
                else:
                    break
            else:
                optimized_results.append(result)
                current_tokens += content_tokens

        return optimized_results, {
            "strategy": "truncate_old",
            "action": "truncated",
            "truncation_count": truncation_count,
            "final_token_count": current_tokens,
        }

    def _summarize_long_content(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Summarize long content to reduce tokens."""
        optimized_results = []
        summarized_count = 0

        for result in results:
            content = result.get("content", "")
            content_tokens = self.count_tokens(content)

            if content_tokens > 500:  # Summarize content longer than 500 tokens
                summary = self._create_quick_summary(content)
                result_copy = result.copy()
                result_copy["content"] = summary + " [auto-summarized]"
                optimized_results.append(result_copy)
                summarized_count += 1
            else:
                optimized_results.append(result)

        return optimized_results, {
            "strategy": "summarize_content",
            "action": "summarized",
            "summarized_count": summarized_count,
        }

    def _chunk_large_response(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Chunk large response into manageable pieces."""
        if not results:
            return results, {"strategy": "chunk_response", "action": "no_results"}

        # Estimate total tokens
        total_tokens = sum(
            self.count_tokens(str(result.get("content", ""))) for result in results
        )

        if total_tokens <= max_tokens:
            return results, {
                "strategy": "chunk_response",
                "action": "no_chunking_needed",
            }

        # Create chunks
        chunks = []
        current_chunk = []
        current_chunk_tokens = 0

        for result in results:
            result_tokens = self.count_tokens(str(result.get("content", "")))

            if current_chunk_tokens + result_tokens > self.chunk_size and current_chunk:
                chunks.append(current_chunk.copy())
                current_chunk = [result]
                current_chunk_tokens = result_tokens
            else:
                current_chunk.append(result)
                current_chunk_tokens += result_tokens

        if current_chunk:
            chunks.append(current_chunk)

        # Return first chunk and create cache entry for the rest
        if chunks:
            cache_key = self._create_chunk_cache_entry(chunks)
            return chunks[0], {
                "strategy": "chunk_response",
                "action": "chunked",
                "total_chunks": len(chunks),
                "current_chunk": 1,
                "cache_key": cache_key,
                "has_more": len(chunks) > 1,
            }

        return results, {"strategy": "chunk_response", "action": "failed"}

    def _filter_duplicate_content(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Filter out duplicate or very similar content."""
        if not results:
            return results, {"strategy": "filter_duplicates", "action": "no_results"}

        seen_hashes = set()
        unique_results = []
        duplicates_removed = 0

        for result in results:
            content = result.get("content", "")
            # Create hash of normalized content
            normalized_content = re.sub(r"\s+", " ", content.lower().strip())
            content_hash = hashlib.md5(normalized_content.encode()).hexdigest()

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_results.append(result)
            else:
                duplicates_removed += 1

        return unique_results, {
            "strategy": "filter_duplicates",
            "action": "filtered",
            "duplicates_removed": duplicates_removed,
        }

    def _prioritize_recent_content(
        self,
        results: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Prioritize recent content and score-based ranking."""
        if not results:
            return results, {"strategy": "prioritize_recent", "action": "no_results"}

        # Calculate priority scores
        now = datetime.now()
        scored_results = []

        for result in results:
            score = 0.0

            # Recency score (0-0.5)
            try:
                timestamp = datetime.fromisoformat(result.get("timestamp", ""))
                days_old = (now - timestamp).days
                recency_score = max(0, 0.5 - (days_old / 365) * 0.5)
                score += recency_score
            except (ValueError, TypeError):
                score += 0.1  # Default low recency score

            # Relevance score if available (0-0.3)
            if "score" in result:
                score += result["score"] * 0.3

            # Length penalty for very long content (0 to -0.2)
            content = result.get("content", "")
            if len(content) > 2000:
                score -= 0.2
            elif len(content) > 1000:
                score -= 0.1

            # Code/technical content bonus (0-0.2)
            if any(
                keyword in content.lower()
                for keyword in ["def ", "class ", "function", "error", "exception"]
            ):
                score += 0.2

            scored_results.append((score, result))

        # Sort by priority score and take top results within token limit
        scored_results.sort(key=lambda x: x[0], reverse=True)

        prioritized_results = []
        current_tokens = 0

        for score, result in scored_results:
            result_tokens = self.count_tokens(str(result.get("content", "")))
            if current_tokens + result_tokens <= max_tokens:
                prioritized_results.append(result)
                current_tokens += result_tokens
            else:
                break

        return prioritized_results, {
            "strategy": "prioritize_recent",
            "action": "prioritized",
            "final_token_count": current_tokens,
        }

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncate content to fit within token limit."""
        if self.count_tokens(content) <= max_tokens:
            return content

        # Try to truncate at sentence boundaries
        sentences = content.split(". ")
        truncated = ""

        for sentence in sentences:
            test_content = truncated + sentence + ". "
            if self.count_tokens(test_content) <= max_tokens:
                truncated = test_content
            else:
                break

        if not truncated:
            # Fallback to character-based truncation
            if self.encoding:
                tokens = self.encoding.encode(content)[:max_tokens]
                truncated = self.encoding.decode(tokens)
            else:
                # Rough character limit
                char_limit = max_tokens * 4
                truncated = content[:char_limit]

        return truncated.strip()

    def _create_quick_summary(self, content: str, max_length: int = 200) -> str:
        """Create a quick summary of content."""
        # Extract first and last sentences
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        if not sentences:
            return content[:max_length]

        if len(sentences) == 1:
            return sentences[0][:max_length]

        first_sentence = sentences[0]
        last_sentence = sentences[-1]

        summary = f"{first_sentence}. ... {last_sentence}"
        if len(summary) > max_length:
            summary = first_sentence[: max_length - 3] + "..."

        return summary

    def _create_chunk_cache_entry(self, chunks: list[list[dict[str, Any]]]) -> str:
        """Create cache entry for chunked results."""
        cache_key = hashlib.md5(
            f"chunks_{datetime.now().isoformat()}_{len(chunks)}".encode(),
        ).hexdigest()

        chunk_result = ChunkResult(
            chunks=[json.dumps(chunk) for chunk in chunks],
            total_chunks=len(chunks),
            current_chunk=1,
            cache_key=cache_key,
            metadata={
                "created": datetime.now().isoformat(),
                "expires": (datetime.now() + timedelta(hours=1)).isoformat(),
            },
        )

        self.chunk_cache[cache_key] = chunk_result
        return cache_key

    def get_chunk(self, cache_key: str, chunk_index: int) -> dict[str, Any] | None:
        """Get a specific chunk from cache."""
        if cache_key not in self.chunk_cache:
            return None

        chunk_result = self.chunk_cache[cache_key]

        # Check expiration
        try:
            expires = datetime.fromisoformat(chunk_result.metadata["expires"])
            if datetime.now() > expires:
                del self.chunk_cache[cache_key]
                return None
        except (ValueError, KeyError):
            pass

        if 1 <= chunk_index <= len(chunk_result.chunks):
            chunk_data = json.loads(chunk_result.chunks[chunk_index - 1])
            return {
                "chunk": chunk_data,
                "current_chunk": chunk_index,
                "total_chunks": chunk_result.total_chunks,
                "cache_key": cache_key,
                "has_more": chunk_index < chunk_result.total_chunks,
            }

        return None

    def _calculate_token_savings(
        self,
        original: list[dict[str, Any]],
        optimized: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Calculate token savings from optimization."""
        original_tokens = sum(
            self.count_tokens(str(item.get("content", ""))) for item in original
        )
        optimized_tokens = sum(
            self.count_tokens(str(item.get("content", ""))) for item in optimized
        )

        return {
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "tokens_saved": original_tokens - optimized_tokens,
            "savings_percentage": round(
                ((original_tokens - optimized_tokens) / original_tokens) * 100,
                1,
            )
            if original_tokens > 0
            else 0,
        }

    def track_usage(
        self,
        operation: str,
        request_tokens: int,
        response_tokens: int,
        optimization_applied: str | None = None,
    ) -> None:
        """Track token usage for monitoring."""
        metrics = TokenUsageMetrics(
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=request_tokens + response_tokens,
            timestamp=datetime.now().isoformat(),
            operation=operation,
            optimization_applied=optimization_applied,
        )

        self.usage_history.append(metrics)

        # Keep only last 100 entries
        if len(self.usage_history) > 100:
            self.usage_history = self.usage_history[-100:]

    def get_usage_stats(self, hours: int = 24) -> dict[str, Any]:
        """Get token usage statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)

        recent_usage = [
            m
            for m in self.usage_history
            if datetime.fromisoformat(m.timestamp) > cutoff
        ]

        if not recent_usage:
            return {"status": "no_data", "period_hours": hours}

        total_tokens = sum(m.total_tokens for m in recent_usage)
        avg_tokens = total_tokens / len(recent_usage)

        # Count optimizations applied
        optimizations = {}
        for metric in recent_usage:
            if metric.optimization_applied:
                optimizations[metric.optimization_applied] = (
                    optimizations.get(metric.optimization_applied, 0) + 1
                )

        return {
            "status": "success",
            "period_hours": hours,
            "total_requests": len(recent_usage),
            "total_tokens": total_tokens,
            "average_tokens_per_request": round(avg_tokens, 1),
            "optimizations_applied": optimizations,
            "estimated_cost_savings": self._estimate_cost_savings(recent_usage),
        }

    def _estimate_cost_savings(
        self,
        usage_metrics: list[TokenUsageMetrics],
    ) -> dict[str, float]:
        """Estimate cost savings from optimizations."""
        # Rough cost estimation (adjust based on actual pricing)
        cost_per_1k_tokens = 0.01  # Example rate

        optimized_requests = [m for m in usage_metrics if m.optimization_applied]
        if not optimized_requests:
            return {"savings_usd": 0.0, "requests_optimized": 0}

        # Estimate 20-40% token savings from optimization
        estimated_savings_tokens = sum(m.total_tokens * 0.3 for m in optimized_requests)
        estimated_savings_usd = (estimated_savings_tokens / 1000) * cost_per_1k_tokens

        return {
            "savings_usd": round(estimated_savings_usd, 4),
            "requests_optimized": len(optimized_requests),
            "estimated_tokens_saved": int(estimated_savings_tokens),
        }

    def cleanup_cache(self, max_age_hours: int = 1):
        """Clean up expired cache entries."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        expired_keys = []

        for key, chunk_result in self.chunk_cache.items():
            try:
                expires = datetime.fromisoformat(chunk_result.metadata["expires"])
                if expires < cutoff:
                    expired_keys.append(key)
            except (ValueError, KeyError):
                expired_keys.append(key)  # Remove entries with invalid expiration

        for key in expired_keys:
            del self.chunk_cache[key]

        return len(expired_keys)


# Global optimizer instance
_token_optimizer = None


def get_token_optimizer() -> TokenOptimizer:
    """Get global token optimizer instance."""
    global _token_optimizer
    if _token_optimizer is None:
        _token_optimizer = TokenOptimizer()
    return _token_optimizer


async def optimize_search_response(
    results: list[dict[str, Any]],
    strategy: str = "prioritize_recent",
    max_tokens: int = 4000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Async wrapper for search result optimization."""
    optimizer = get_token_optimizer()
    return optimizer.optimize_search_results(results, strategy, max_tokens)


async def get_cached_chunk(cache_key: str, chunk_index: int) -> dict[str, Any] | None:
    """Async wrapper for chunk retrieval."""
    optimizer = get_token_optimizer()
    return optimizer.get_chunk(cache_key, chunk_index)


async def track_token_usage(
    operation: str,
    request_tokens: int,
    response_tokens: int,
    optimization_applied: str | None = None,
) -> None:
    """Async wrapper for usage tracking."""
    optimizer = get_token_optimizer()
    optimizer.track_usage(
        operation,
        request_tokens,
        response_tokens,
        optimization_applied,
    )


async def get_token_usage_stats(hours: int = 24) -> dict[str, Any]:
    """Async wrapper for usage statistics."""
    optimizer = get_token_optimizer()
    return optimizer.get_usage_stats(hours)

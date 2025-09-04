#!/usr/bin/env python3
"""Quality analysis utilities for session management.

This module provides quality assessment and analysis functionality following
crackerjack architecture patterns with single responsibility principle.
"""

from __future__ import annotations

from typing import Any


def _extract_quality_scores(reflections: list[dict[str, Any]]) -> list[float]:
    """Extract quality scores from reflection data."""
    scores = []

    for reflection in reflections:
        try:
            # Look for quality score in reflection content or metadata
            content = reflection.get("content", "").lower()

            # Parse common quality score formats
            if "quality score:" in content:
                # Extract score after "quality score:"
                parts = content.split("quality score:")
                if len(parts) > 1:
                    score_text = parts[1].split()[0]  # Get first word after
                    # Handle formats like "85/100", "0.85", "85"
                    if "/" in score_text:
                        numerator = float(score_text.split("/")[0])
                        denominator = float(score_text.split("/")[1])
                        score = (numerator / denominator) * 100
                    elif "." in score_text and float(score_text) <= 1.0:
                        score = float(score_text) * 100
                    else:
                        score = float(score_text)

                    if 0 <= score <= 100:
                        scores.append(score)

            # Check metadata for score
            metadata = reflection.get("metadata", {})
            if "quality_score" in metadata:
                score = float(metadata["quality_score"])
                if 0 <= score <= 100:
                    scores.append(score)

        except (ValueError, TypeError, AttributeError):
            # Skip malformed scores
            continue

    return scores


def _analyze_quality_trend(quality_scores: list[float]) -> tuple[str, list[str], bool]:
    """Analyze quality trend from historical scores."""
    if len(quality_scores) < 2:
        return "insufficient_data", ["Not enough data to analyze trend"], False

    # Calculate trend
    recent_scores = quality_scores[-5:]  # Last 5 scores
    older_scores = (
        quality_scores[-10:-5] if len(quality_scores) >= 10 else quality_scores[:-5]
    )

    if not older_scores:
        return "stable", ["Initial quality baseline established"], True

    recent_avg = sum(recent_scores) / len(recent_scores)
    older_avg = sum(older_scores) / len(older_scores)

    difference = recent_avg - older_avg
    insights = []
    improving = False

    if difference > 5:
        trend = "improving"
        improving = True
        insights.extend(
            [
                f"📈 Quality improving: +{difference:.1f} points",
                "🎯 Continue current development practices",
            ]
        )
    elif difference < -5:
        trend = "declining"
        insights.extend(
            [
                f"📉 Quality declining: {difference:.1f} points",
                "⚠️ Review recent changes and processes",
            ]
        )
    else:
        trend = "stable"
        improving = True
        insights.extend(
            [
                f"📊 Quality stable: {difference:+.1f} points variation",
                "✅ Maintaining consistent development standards",
            ]
        )

    # Add specific recommendations based on score level
    current_score = recent_scores[-1] if recent_scores else 0
    if current_score < 70:
        insights.append("🔧 Focus on code quality improvements")
    elif current_score > 90:
        insights.append("⭐ Excellent quality standards maintained")

    return trend, insights, improving


def _extract_quality_scores_from_reflections(
    reflections: list[dict[str, Any]],
) -> list[float]:
    """Enhanced quality score extraction with multiple parsing strategies."""
    scores = []

    for reflection in reflections:
        try:
            content = reflection.get("content", "").lower()

            # Strategy 1: Direct quality score mentions
            quality_patterns = [
                "quality score:",
                "code quality:",
                "overall score:",
                "quality rating:",
            ]

            for pattern in quality_patterns:
                if pattern in content:
                    parts = content.split(pattern)
                    if len(parts) > 1:
                        score_text = parts[1].strip().split()[0]
                        score = _parse_score_text(score_text)
                        if score is not None:
                            scores.append(score)
                            break  # Use first valid score found

            # Strategy 2: Checkpoint metadata
            metadata = reflection.get("metadata", {})
            for key in ["quality_score", "score", "checkpoint_score"]:
                if key in metadata:
                    try:
                        score = float(metadata[key])
                        if 0 <= score <= 100:
                            scores.append(score)
                            break
                    except (ValueError, TypeError):
                        continue

        except Exception:
            # Skip problematic reflections
            continue

    return scores


def _parse_score_text(score_text: str) -> float | None:
    """Parse various score text formats into normalized 0-100 score."""
    try:
        score_text = score_text.replace(",", "").strip()

        # Handle fraction format (85/100)
        if "/" in score_text:
            parts = score_text.split("/")
            if len(parts) == 2:
                numerator = float(parts[0])
                denominator = float(parts[1])
                if denominator > 0:
                    score = (numerator / denominator) * 100
                    return score if 0 <= score <= 100 else None

        # Handle decimal format (0.85)
        elif "." in score_text:
            score = float(score_text)
            if 0 <= score <= 1.0:
                return score * 100
            if 0 <= score <= 100:
                return score

        # Handle integer format (85)
        else:
            score = float(score_text)
            return score if 0 <= score <= 100 else None

    except (ValueError, IndexError):
        return None

    return None


def _generate_quality_trend_recommendations(scores: list[float]) -> list[str]:
    """Generate specific recommendations based on quality trend analysis."""
    if not scores:
        return ["📊 Start tracking quality metrics for trend analysis"]

    recommendations = []
    current_score = scores[-1]

    # Score-based recommendations
    if current_score < 60:
        recommendations.extend(
            [
                "🚨 Critical: Immediate quality improvement needed",
                "• Run comprehensive code review and testing",
                "• Focus on reducing technical debt",
                "• Consider pair programming for complex changes",
            ]
        )
    elif current_score < 75:
        recommendations.extend(
            [
                "⚠️ Quality below target: Focus on improvement",
                "• Increase test coverage and documentation",
                "• Review and refactor complex code sections",
            ]
        )
    elif current_score < 90:
        recommendations.extend(
            [
                "✅ Good quality: Minor optimizations available",
                "• Fine-tune linting and formatting rules",
                "• Enhance error handling and logging",
            ]
        )
    else:
        recommendations.extend(
            [
                "⭐ Excellent quality: Maintain current standards",
                "• Share best practices with team",
                "• Document successful patterns for reuse",
            ]
        )

    # Trend-based recommendations
    if len(scores) >= 3:
        recent_trend = scores[-3:]
        if all(
            recent_trend[i] < recent_trend[i + 1] for i in range(len(recent_trend) - 1)
        ):
            recommendations.append("📈 Positive trend: Continue current practices")
        elif all(
            recent_trend[i] > recent_trend[i + 1] for i in range(len(recent_trend) - 1)
        ):
            recommendations.append("📉 Declining trend: Review recent changes")

    return recommendations


def _get_time_based_recommendations(hour: int) -> list[str]:
    """Generate recommendations based on current time of day."""
    recommendations = []

    if 6 <= hour < 12:  # Morning
        recommendations.extend(
            [
                "🌅 Morning session: Good time for complex problem-solving",
                "• Focus on architecture and design decisions",
                "• Plan day's development priorities",
            ]
        )
    elif 12 <= hour < 17:  # Afternoon
        recommendations.extend(
            [
                "☀️ Afternoon session: Peak productivity time",
                "• Implement planned features and fixes",
                "• Conduct code reviews and testing",
            ]
        )
    elif 17 <= hour < 21:  # Evening
        recommendations.extend(
            [
                "🌆 Evening session: Good for documentation and cleanup",
                "• Update documentation and comments",
                "• Refactor and optimize existing code",
            ]
        )
    else:  # Late night/early morning
        recommendations.extend(
            [
                "🌙 Late session: Focus on simple, well-tested changes",
                "• Avoid complex architectural changes",
                "• Consider shorter development sessions",
            ]
        )

    return recommendations


def _ensure_default_recommendations(priority_actions: list[str]) -> list[str]:
    """Ensure there are always some recommendations available."""
    if not priority_actions:
        return [
            "🎯 Focus on current development goals",
            "📝 Keep documentation updated",
            "🧪 Maintain test coverage",
            "🔍 Regular code quality checks",
        ]
    return priority_actions


def _get_intelligence_error_result(error: Exception) -> dict[str, Any]:
    """Generate error result for intelligence system failures."""
    return {
        "success": False,
        "error": f"Intelligence system error: {error}",
        "recommendations": [
            "⚠️ Intelligence features temporarily unavailable",
            "• Basic session management tools still functional",
            "• Manual quality assessment recommended",
            "• Check system dependencies and configuration",
        ],
        "fallback_mode": True,
    }

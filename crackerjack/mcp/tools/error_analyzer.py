import typing as t
from contextlib import suppress


def analyze_errors_with_caching(
    context: t.Any, use_cache: bool = True
) -> dict[str, t.Any]:
    try:
        cached_patterns = _get_cached_patterns(context, use_cache)
        return _build_error_analysis(cached_patterns, context)

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error analysis failed: {e}",
            "recommendations": [],
            "patterns": [],
        }


def _get_cached_patterns(context: t.Any, use_cache: bool) -> list[t.Any]:
    if not use_cache:
        return []

    with suppress(Exception):
        cache = getattr(context, "cache", None)
        if cache and hasattr(cache, "get_error_patterns"):
            patterns: list[t.Any] = cache.get_error_patterns()
            return patterns

    return []


def _build_error_analysis(patterns: list[t.Any], context: t.Any) -> dict[str, t.Any]:
    analysis = {
        "status": "success",
        "patterns_found": len(patterns),
        "recommendations": [],
        "error_categories": {},
        "fix_suggestions": [],
        "urgency_level": "low",
    }

    if not patterns:
        analysis.update(
            {
                "message": "No cached error patterns found-this indicates clean execution history",
                "recommendations": [
                    "Continue with current development practices",
                    "Consider running comprehensive quality checks if issues arise",
                ],
            }
        )
        return analysis

    categories = _categorize_error_patterns(patterns)
    analysis["error_categories"] = categories

    recommendations = _generate_error_recommendations(categories)
    analysis["recommendations"] = recommendations

    analysis["urgency_level"] = _calculate_urgency_level(categories)

    analysis["fix_suggestions"] = _generate_fix_suggestions(categories)

    analysis["message"] = (
        f"Found {len(patterns)} cached error patterns across {len(categories)} categories"
    )

    return analysis


def _categorize_error_patterns(patterns: list[t.Any]) -> dict[str, list[t.Any]]:
    categories: dict[str, list[t.Any]] = {
        "syntax_errors": [],
        "import_errors": [],
        "type_errors": [],
        "test_failures": [],
        "security_issues": [],
        "complexity_issues": [],
        "dependency_issues": [],
        "formatting_issues": [],
        "unknown": [],
    }

    for pattern in patterns:
        category = _classify_error_pattern(pattern)
        categories[category].append(pattern)

    return {k: v for k, v in categories.items() if v}


def _classify_error_pattern(pattern: t.Any) -> str:
    pattern_str = str(pattern).lower()

    if any(
        keyword in pattern_str
        for keyword in ("syntax", "invalid syntax", "unexpected token")
    ):
        return "syntax_errors"
    elif any(
        keyword in pattern_str for keyword in ("import", "module", "no module named")
    ):
        return "import_errors"
    elif any(
        keyword in pattern_str for keyword in ("type", "annotation", "mypy", "pyright")
    ):
        return "type_errors"
    elif any(
        keyword in pattern_str for keyword in ("test", "assert", "pytest", "failed")
    ):
        return "test_failures"
    elif any(
        keyword in pattern_str for keyword in ("security", "bandit", "vulnerability")
    ):
        return "security_issues"
    elif any(
        keyword in pattern_str for keyword in ("complexity", "complex", "cognitive")
    ):
        return "complexity_issues"
    elif any(
        keyword in pattern_str for keyword in ("dependency", "requirement", "package")
    ):
        return "dependency_issues"
    elif any(
        keyword in pattern_str for keyword in ("format", "style", "ruff", "black")
    ):
        return "formatting_issues"
    return "unknown"


def _generate_error_recommendations(categories: dict[str, list[t.Any]]) -> list[str]:
    recommendations = []

    if categories.get("syntax_errors"):
        recommendations.append(
            "🔧 Review syntax errors and fix basic Python syntax issues"
        )

    if categories.get("import_errors"):
        recommendations.extend(
            [
                "📦 Check imports and module dependencies",
                "🔍 Verify all required packages are installed",
            ]
        )

    if categories.get("type_errors"):
        recommendations.extend(
            [
                "🏷️ Add missing type annotations",
                "🔧 Fix type mismatches and annotation issues",
            ]
        )

    if categories.get("test_failures"):
        recommendations.extend(
            [
                "🧪 Fix failing tests and improve test reliability",
                "🔬 Review test fixtures and dependencies",
            ]
        )

    if categories.get("security_issues"):
        recommendations.extend(
            [
                "🔒 Address security vulnerabilities immediately",
                "🛡️ Follow security best practices",
            ]
        )

    if categories.get("complexity_issues"):
        recommendations.extend(
            [
                "📐 Refactor complex functions to reduce cognitive load",
                "🔄 Break down large functions into smaller components",
            ]
        )

    if categories.get("dependency_issues"):
        recommendations.extend(
            [
                "📚 Update dependency management",
                "🔄 Review and clean up requirements",
            ]
        )

    if categories.get("formatting_issues"):
        recommendations.extend(
            [
                "💅 Apply code formatting and style fixes",
                "📋 Ensure consistent code style",
            ]
        )

    if len(categories) > 3:
        recommendations.extend(
            [
                "🎯 Consider running AI agent auto-fixing for comprehensive resolution",
                "📊 Monitor quality metrics to prevent regression",
            ]
        )

    return recommendations


def _calculate_urgency_level(categories: dict[str, list[t.Any]]) -> str:
    total_errors = sum(len(errors) for errors in categories.values())

    if categories.get("security_issues"):
        return "high"

    if categories.get("test_failures") and len(categories["test_failures"]) > 5:
        return "high"

    if categories.get("syntax_errors"):
        return "medium"

    if total_errors > 20:
        return "medium"

    if len(categories) > 4:
        return "medium"

    return "low"


def _generate_fix_suggestions(
    categories: dict[str, list[t.Any]],
) -> list[dict[str, str]]:
    suggestions = []

    if categories.get("formatting_issues"):
        suggestions.append(
            {
                "category": "formatting",
                "action": "Run code formatting",
                "command": "python - m crackerjack - - skip-tests",
                "description": "Fix formatting and style issues",
            }
        )

    if categories.get("type_errors"):
        suggestions.append(
            {
                "category": "types",
                "action": "Fix type annotations",
                "command": "python - m crackerjack - - ai-agent",
                "description": "Add missing type hints and resolve type conflicts",
            }
        )

    if categories.get("test_failures"):
        suggestions.append(
            {
                "category": "tests",
                "action": "Fix test failures",
                "command": "python - m crackerjack - t - - ai-agent",
                "description": "Run tests with AI auto-fixing enabled",
            }
        )

    if categories.get("security_issues"):
        suggestions.append(
            {
                "category": "security",
                "action": "Address security issues",
                "command": "python - m crackerjack - - ai - agent-t",
                "description": "Fix security vulnerabilities with AI assistance",
            }
        )

    if len(categories) > 3:
        suggestions.append(
            {
                "category": "comprehensive",
                "action": "Full quality check with AI fixing",
                "command": "python - m crackerjack - - ai - agent-t",
                "description": "Comprehensive quality check with autonomous fixing",
            }
        )

    return suggestions

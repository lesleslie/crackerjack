#!/usr/bin/env python3
"""Enhanced Search Capabilities for Session Management MCP Server.

Provides multi-modal search including code snippets, error patterns, and time-based queries.
"""

import ast
import re
from datetime import datetime, timedelta
from typing import Any

try:
    from dateutil.parser import parse as parse_date
    from dateutil.relativedelta import relativedelta

    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

from .reflection_tools import ReflectionDatabase


class CodeSearcher:
    """AST-based code search for Python code snippets."""

    def __init__(self) -> None:
        self.search_types = {
            "function": ast.FunctionDef,
            "class": ast.ClassDef,
            "import": (ast.Import, ast.ImportFrom),
            "assignment": ast.Assign,
            "call": ast.Call,
            "loop": (ast.For, ast.While),
            "conditional": ast.If,
            "try": ast.Try,
            "async": (ast.AsyncFunctionDef, ast.AsyncWith, ast.AsyncFor),
        }

    def extract_code_patterns(self, content: str) -> list[dict[str, Any]]:
        """Extract code patterns from conversation content."""
        patterns = []

        # Extract Python code blocks
        code_blocks = re.findall(r"```python\n(.*?)\n```", content, re.DOTALL)
        code_blocks.extend(re.findall(r"```\n(.*?)\n```", content, re.DOTALL))

        for i, code in enumerate(code_blocks):
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    for pattern_type, node_types in self.search_types.items():
                        if isinstance(node, node_types):
                            pattern_info = {
                                "type": pattern_type,
                                "content": code,
                                "block_index": i,
                                "line_number": getattr(node, "lineno", 0),
                            }

                            # Extract specific information based on node type
                            if isinstance(node, ast.FunctionDef):
                                pattern_info["name"] = node.name
                                pattern_info["args"] = [
                                    arg.arg for arg in node.args.args
                                ]
                            elif isinstance(node, ast.ClassDef):
                                pattern_info["name"] = node.name
                            elif isinstance(node, ast.Import | ast.ImportFrom):
                                if isinstance(node, ast.Import):
                                    pattern_info["modules"] = [
                                        alias.name for alias in node.names
                                    ]
                                else:
                                    pattern_info["module"] = node.module
                                    pattern_info["names"] = [
                                        alias.name for alias in node.names
                                    ]

                            patterns.append(pattern_info)

            except (SyntaxError, ValueError):
                # Not valid Python code, skip
                continue

        return patterns


class ErrorPatternMatcher:
    """Pattern matching for error messages and debugging contexts."""

    def __init__(self) -> None:
        self.error_patterns = {
            "python_traceback": r"Traceback \(most recent call last\):.*?(?=\n\n|\Z)",
            "python_exception": r"(\w+Error): (.+)",
            "javascript_error": r"(Error|TypeError|ReferenceError): (.+)",
            "compile_error": r"(error|Error): (.+) at line (\d+)",
            "warning": r"(warning|Warning): (.+)",
            "assertion": r"AssertionError: (.+)",
            "import_error": r"ImportError: (.+)",
            "module_not_found": r"ModuleNotFoundError: (.+)",
            "file_not_found": r"FileNotFoundError: (.+)",
            "permission_denied": r"PermissionError: (.+)",
            "network_error": r"(ConnectionError|TimeoutError|HTTPError): (.+)",
        }

        self.context_patterns = {
            "debugging": r"(debug|debugging|breakpoint|pdb|print\()",
            "testing": r"(test|pytest|unittest|assert|mock)",
            "error_handling": r"(try|except|finally|raise|catch)",
            "performance": r"(slow|performance|benchmark|optimize|profil)",
            "security": r"(security|authentication|authorization|token|password)",
        }

    def extract_error_patterns(self, content: str) -> list[dict[str, Any]]:
        """Extract error patterns and debugging context from content."""
        patterns = []

        # Find error patterns
        for pattern_name, regex in self.error_patterns.items():
            matches = re.finditer(regex, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                patterns.append(
                    {
                        "type": "error",
                        "subtype": pattern_name,
                        "content": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "groups": match.groups() if match.groups() else [],
                    },
                )

        # Find context patterns
        for context_name, regex in self.context_patterns.items():
            if re.search(regex, content, re.IGNORECASE):
                patterns.append(
                    {
                        "type": "context",
                        "subtype": context_name,
                        "content": content,
                        "relevance": "high"
                        if context_name in ["debugging", "error_handling"]
                        else "medium",
                    },
                )

        return patterns


class TemporalSearchParser:
    """Parse natural language time expressions for conversation search."""

    def __init__(self) -> None:
        self.relative_patterns = {
            "today": timedelta(hours=0),
            "yesterday": timedelta(days=1),
            "this week": timedelta(weeks=1),
            "last week": timedelta(weeks=1, days=7),
            "this month": relativedelta(months=1)
            if DATEUTIL_AVAILABLE
            else timedelta(days=30),
            "last month": relativedelta(months=2)
            if DATEUTIL_AVAILABLE
            else timedelta(days=60),
            "this year": relativedelta(years=1)
            if DATEUTIL_AVAILABLE
            else timedelta(days=365),
        }

        self.time_patterns = [
            r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago",
            r"(today|yesterday|this\s+week|last\s+week|this\s+month|last\s+month)",
            r"since\s+(today|yesterday|this\s+week|last\s+week)",
            r"in\s+the\s+last\s+(\d+)\s+(minute|hour|day|week|month|year)s?",
            r"(\d{4}-\d{2}-\d{2})",  # ISO date
            r"(\d{1,2}/\d{1,2}/\d{4})",  # MM/DD/YYYY
        ]

    def _calculate_delta(self, amount: int, unit: str) -> timedelta:
        """Calculate timedelta from amount and unit."""
        if unit == "minute":
            return timedelta(minutes=amount)
        if unit == "hour":
            return timedelta(hours=amount)
        if unit == "day":
            return timedelta(days=amount)
        if unit == "week":
            return timedelta(weeks=amount)
        if unit == "month":
            return (
                relativedelta(months=amount)
                if DATEUTIL_AVAILABLE
                else timedelta(days=amount * 30)
            )
        if unit == "year":
            return (
                relativedelta(years=amount)
                if DATEUTIL_AVAILABLE
                else timedelta(days=amount * 365)
            )
        return timedelta()

    def _parse_relative_patterns(
        self,
        expression: str,
        now: datetime,
    ) -> tuple[datetime | None, datetime | None]:
        """Parse relative time patterns."""
        for pattern, delta in self.relative_patterns.items():
            if pattern in expression:
                if "last" in pattern or pattern == "yesterday":
                    end_time = now - delta
                    start_time = end_time - delta
                else:
                    start_time = now - delta
                    end_time = now
                return start_time, end_time
        return None, None

    def _parse_ago_pattern(
        self,
        expression: str,
        now: datetime,
    ) -> tuple[datetime | None, datetime | None]:
        """Parse 'X time units ago' pattern."""
        match = re.search(
            r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago",
            expression,
        )
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            delta = self._calculate_delta(amount, unit)
            end_time = now - delta
            return end_time, now
        return None, None

    def _parse_last_pattern(
        self,
        expression: str,
        now: datetime,
    ) -> tuple[datetime | None, datetime | None]:
        """Parse 'in the last X units' pattern."""
        match = re.search(
            r"in\s+the\s+last\s+(\d+)\s+(minute|hour|day|week|month|year)s?",
            expression,
        )
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            delta = self._calculate_delta(amount, unit)
            start_time = now - delta
            return start_time, now
        return None, None

    def _parse_absolute_date(
        self,
        expression: str,
    ) -> tuple[datetime | None, datetime | None]:
        """Parse absolute date expressions."""
        if not DATEUTIL_AVAILABLE:
            return None, None

        try:
            parsed_date = parse_date(expression)
            # Return day range (start of day to end of day)
            start_time = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
            return start_time, end_time
        except (ValueError, TypeError):
            return None, None

    def parse_time_expression(
        self,
        expression: str,
    ) -> tuple[datetime | None, datetime | None]:
        """Parse time expression into start and end datetime."""
        expression = expression.lower().strip()
        now = datetime.now()

        # Try different parsing strategies
        parsers = [
            self._parse_relative_patterns,
            self._parse_ago_pattern,
            self._parse_last_pattern,
            lambda expr, dt: self._parse_absolute_date(expr),
        ]

        for parser in parsers:
            result = parser(expression, now)
            if result != (None, None):
                return result

        return None, None


class EnhancedSearchEngine:
    """Main search engine that combines all enhanced search capabilities."""

    def __init__(self, reflection_db: ReflectionDatabase) -> None:
        self.reflection_db = reflection_db
        self.code_searcher = CodeSearcher()
        self.error_matcher = ErrorPatternMatcher()
        self.temporal_parser = TemporalSearchParser()

    async def search_code_patterns(
        self,
        query: str,
        pattern_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for code patterns in conversations."""
        results = []

        # Get all conversations from database
        if hasattr(self.reflection_db, "conn") and self.reflection_db.conn:
            cursor = self.reflection_db.conn.execute(
                "SELECT id, content, project, timestamp, metadata FROM conversations",
            )
            conversations = cursor.fetchall()

            for conv in conversations:
                conv_id, content, project, timestamp, metadata = conv
                patterns = self.code_searcher.extract_code_patterns(content)

                for pattern in patterns:
                    if pattern_type and pattern["type"] != pattern_type:
                        continue

                    # Calculate relevance based on query similarity
                    relevance = self._calculate_code_relevance(pattern, query)

                    if relevance > 0.3:  # Threshold for relevance
                        results.append(
                            {
                                "conversation_id": conv_id,
                                "project": project,
                                "timestamp": timestamp,
                                "pattern": pattern,
                                "relevance": relevance,
                                "snippet": content[:500] + "..."
                                if len(content) > 500
                                else content,
                            },
                        )

        # Sort by relevance and limit results
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]

    async def search_error_patterns(
        self,
        query: str,
        error_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for error patterns and debugging contexts."""
        results = []

        if hasattr(self.reflection_db, "conn") and self.reflection_db.conn:
            cursor = self.reflection_db.conn.execute(
                "SELECT id, content, project, timestamp, metadata FROM conversations",
            )
            conversations = cursor.fetchall()

            for conv in conversations:
                conv_id, content, project, timestamp, metadata = conv
                patterns = self.error_matcher.extract_error_patterns(content)

                for pattern in patterns:
                    if error_type and pattern["subtype"] != error_type:
                        continue

                    # Calculate relevance based on query similarity
                    relevance = self._calculate_error_relevance(pattern, query)

                    if relevance > 0.2:  # Lower threshold for errors
                        results.append(
                            {
                                "conversation_id": conv_id,
                                "project": project,
                                "timestamp": timestamp,
                                "pattern": pattern,
                                "relevance": relevance,
                                "snippet": content[:500] + "..."
                                if len(content) > 500
                                else content,
                            },
                        )

        # Sort by relevance and limit results
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]

    async def search_temporal(
        self,
        time_expression: str,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search conversations within a time range."""
        start_time, end_time = self.temporal_parser.parse_time_expression(
            time_expression,
        )

        if not start_time or not end_time:
            return [{"error": f"Could not parse time expression: {time_expression}"}]

        results = []

        if hasattr(self.reflection_db, "conn") and self.reflection_db.conn:
            # Convert to ISO format for database query
            start_iso = start_time.isoformat()
            end_iso = end_time.isoformat()

            sql_query = """
                SELECT id, content, project, timestamp, metadata
                FROM conversations
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """

            cursor = self.reflection_db.conn.execute(sql_query, (start_iso, end_iso))
            conversations = cursor.fetchall()

            for conv in conversations:
                conv_id, content, project, timestamp, metadata = conv

                # If query provided, filter by content relevance
                if query:
                    relevance = self._calculate_text_relevance(content, query)
                    if relevance < 0.3:
                        continue
                else:
                    relevance = 1.0

                results.append(
                    {
                        "conversation_id": conv_id,
                        "project": project,
                        "timestamp": timestamp,
                        "content": content[:500] + "..."
                        if len(content) > 500
                        else content,
                        "relevance": relevance,
                    },
                )

        return results[:limit]

    def _calculate_code_relevance(self, pattern: dict[str, Any], query: str) -> float:
        """Calculate relevance score for code patterns."""
        relevance = 0.0
        query_lower = query.lower()

        # Type matching
        if pattern["type"] in query_lower:
            relevance += 0.5

        # Name matching (for functions/classes)
        if "name" in pattern and pattern["name"].lower() in query_lower:
            relevance += 0.7

        # Content matching
        if query_lower in pattern["content"].lower():
            relevance += 0.4

        # Module/import matching
        if "modules" in pattern:
            for module in pattern["modules"]:
                if module.lower() in query_lower:
                    relevance += 0.3

        return min(relevance, 1.0)

    def _calculate_error_relevance(self, pattern: dict[str, Any], query: str) -> float:
        """Calculate relevance score for error patterns."""
        relevance = 0.0
        query_lower = query.lower()

        # Error type matching
        if pattern["subtype"] in query_lower:
            relevance += 0.6

        # Content matching
        if "content" in pattern and query_lower in pattern["content"].lower():
            relevance += 0.5

        # Context relevance boost
        if pattern["type"] == "context" and pattern.get("relevance") == "high":
            relevance += 0.3

        return min(relevance, 1.0)

    def _calculate_text_relevance(self, content: str, query: str) -> float:
        """Simple text relevance calculation."""
        query_lower = query.lower()
        content_lower = content.lower()

        # Simple keyword matching
        query_words = query_lower.split()
        content_words = content_lower.split()

        matches = sum(1 for word in query_words if word in content_words)
        return matches / len(query_words) if query_words else 0.0

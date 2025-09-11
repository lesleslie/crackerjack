#!/usr/bin/env python3
"""Advanced Search Engine for Session Management.

Provides enhanced search capabilities with faceted filtering, full-text search,
and intelligent result ranking.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .reflection_tools import ReflectionDatabase
from .search_enhanced import EnhancedSearchEngine
from .utils.regex_patterns import SAFE_PATTERNS


@dataclass
class SearchFilter:
    """Represents a search filter criterion."""

    field: str
    operator: str  # 'eq', 'ne', 'in', 'not_in', 'contains', 'starts_with', 'ends_with', 'range'
    value: str | list[str] | tuple[Any, Any]
    negate: bool = False


@dataclass
class SearchFacet:
    """Represents a search facet with possible values."""

    name: str
    values: list[tuple[str, int]]  # (value, count) tuples
    facet_type: str = "terms"  # 'terms', 'range', 'date'


@dataclass
class SearchResult:
    """Enhanced search result with metadata."""

    content_id: str
    content_type: str
    title: str
    content: str
    score: float
    project: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    highlights: list[str] = field(default_factory=list)
    facets: dict[str, Any] = field(default_factory=dict)


class AdvancedSearchEngine:
    """Advanced search engine with faceted filtering and full-text search."""

    def __init__(self, reflection_db: ReflectionDatabase) -> None:
        self.reflection_db = reflection_db
        self.enhanced_search = EnhancedSearchEngine(reflection_db)
        self.index_cache: dict[str, datetime] = {}

        # Search configuration
        self.facet_configs = {
            "project": {"type": "terms", "size": 20},
            "content_type": {"type": "terms", "size": 10},
            "date_range": {
                "type": "date",
                "ranges": ["1d", "7d", "30d", "90d", "365d"],
            },
            "author": {"type": "terms", "size": 15},
            "tags": {"type": "terms", "size": 25},
            "file_type": {"type": "terms", "size": 10},
            "language": {"type": "terms", "size": 10},
            "error_type": {"type": "terms", "size": 15},
        }

    async def search(
        self,
        query: str,
        filters: list[SearchFilter] | None = None,
        facets: list[str] | None = None,
        sort_by: str = "relevance",  # 'relevance', 'date', 'project'
        limit: int = 20,
        offset: int = 0,
        include_highlights: bool = True,
        content_type: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, Any]:
        """Perform advanced search with faceted filtering."""
        # Ensure search index is up to date
        await self._ensure_search_index()

        # Build search query
        search_query = self._build_search_query(query, filters)

        # Execute search
        results = await self._execute_search(
            search_query, sort_by, limit, offset, filters, content_type, timeframe
        )

        # Add highlights if requested
        if include_highlights:
            results = await self._add_highlights(results, query)

        # Calculate facets if requested
        facet_results = {}
        if facets:
            facet_results = await self._calculate_facets(query, filters, facets)

        return {
            "results": results,
            "facets": facet_results,
            "total": len(results),
            "query": query,
            "filters": [f.__dict__ for f in filters] if filters else [],
            "took": time.time() - time.time(),  # Will be updated with actual timing
        }

    async def suggest_completions(
        self,
        query: str,
        field: str = "indexed_content",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get search completion suggestions."""
        # Simple prefix matching for now - could be enhanced with more sophisticated algorithms
        # Map friendly field names to actual database column names
        field_map = {
            "content": "indexed_content",
            "project": "JSON_EXTRACT_STRING(search_metadata, '$.project')",
            "tags": "JSON_EXTRACT_STRING(search_metadata, '$.tags')",
        }

        # Use the mapped field name or the original if not in map
        db_field = field_map.get(field, field)

        sql = f"""
            SELECT DISTINCT {db_field}, COUNT(*) as frequency
            FROM search_index
            WHERE {db_field} LIKE ?
            GROUP BY {db_field}
            ORDER BY frequency DESC, {db_field}
            LIMIT ?
        """

        if not self.reflection_db.conn:
            return []

        results = self.reflection_db.conn.execute(
            sql,
            [f"%{query}%", limit],
        ).fetchall()

        suggestions = []
        for row in results:
            suggestions.append({"text": row[0], "frequency": row[1]})

        return suggestions

    async def get_similar_content(
        self,
        content_id: str,
        content_type: str,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Find similar content using embeddings or text similarity."""
        # Get the source content
        sql = """
            SELECT indexed_content, search_metadata
            FROM search_index
            WHERE content_id = ? AND content_type = ?
        """

        if not self.reflection_db.conn:
            return []

        result = self.reflection_db.conn.execute(
            sql,
            [content_id, content_type],
        ).fetchone()

        if not result:
            return []

        source_content = result[0]

        # Use enhanced search for similarity
        similar_results = await self.reflection_db.search_conversations(
            query=source_content[:500],  # Use first 500 chars as query
            limit=limit + 1,  # +1 to exclude the source itself
        )

        # Convert to SearchResult format and exclude source
        search_results = []
        for conv in similar_results:
            if conv.get("conversation_id") != content_id:
                search_results.append(
                    SearchResult(
                        content_id=conv.get("conversation_id", ""),
                        content_type="conversation",
                        title=f"Conversation from {conv.get('project', 'Unknown')}",
                        content=conv.get("content", ""),
                        score=conv.get("score", 0.0),
                        project=conv.get("project"),
                        timestamp=conv.get("timestamp"),
                        metadata=conv.get("metadata", {}),
                    ),
                )

        return search_results[:limit]

    async def search_by_timeframe(
        self,
        timeframe: str,  # '1h', '1d', '1w', '1m', '1y' or ISO date range
        query: str | None = None,
        project: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search within a specific timeframe."""
        # Parse timeframe
        start_time, end_time = self._parse_timeframe(timeframe)

        # Build time filter
        time_filter = SearchFilter(
            field="timestamp",
            operator="range",
            value=(start_time, end_time),
        )

        filters = [time_filter]
        if project:
            filters.append(SearchFilter(field="project", operator="eq", value=project))

        # Perform search
        search_results = await self.search(
            query=query or "*",
            filters=filters,
            limit=limit,
            sort_by="date",
        )

        # Convert SearchResult objects to dictionaries for compatibility
        result_dicts = []
        for result in search_results["results"]:
            result_dict = {
                "content_id": result.content_id,
                "content_type": result.content_type,
                "title": result.title,
                "content": result.content,
                "score": result.score,
                "project": result.project,
                "timestamp": result.timestamp,
                "metadata": result.metadata,
                "highlights": result.highlights,
                "facets": result.facets,
            }
            result_dicts.append(result_dict)

        return result_dicts

    async def aggregate_metrics(
        self,
        metric_type: str,  # 'activity', 'projects', 'content_types', 'errors'
        timeframe: str = "30d",
        filters: list[SearchFilter] | None = None,
    ) -> dict[str, Any]:
        """Calculate aggregate metrics from search data."""
        start_time, end_time = self._parse_timeframe(timeframe)
        base_conditions = ["last_indexed BETWEEN ? AND ?"]
        params: list[datetime | str | int] = [start_time, end_time]

        # Add filter conditions
        if filters:
            filter_conditions, filter_params = self._build_filter_conditions(filters)
            base_conditions.extend(filter_conditions)
            # Convert filter params to appropriate types
            for param in filter_params:
                if isinstance(param, datetime):
                    params.append(param)
                else:
                    # param is str | int, both need to be added as-is
                    params.append(param)

        where_clause = " WHERE " + " AND ".join(base_conditions)

        if metric_type == "activity":
            sql = f"""
                SELECT DATE_TRUNC('day', last_indexed) as day,
                       COUNT(*) as count,
                       COUNT(DISTINCT content_id) as unique_content
                FROM search_index
                {where_clause}
                GROUP BY day
                ORDER BY day
            """

        elif metric_type == "projects":
            sql = f"""
                SELECT JSON_EXTRACT_STRING(search_metadata, '$.project') as project,
                       COUNT(*) as count
                FROM search_index
                {where_clause}
                AND JSON_EXTRACT_STRING(search_metadata, '$.project') IS NOT NULL
                GROUP BY project
                ORDER BY count DESC
            """

        elif metric_type == "content_types":
            sql = f"""
                SELECT content_type, COUNT(*) as count
                FROM search_index
                {where_clause}
                GROUP BY content_type
                ORDER BY count DESC
            """

        elif metric_type == "errors":
            sql = f"""
                SELECT JSON_EXTRACT_STRING(search_metadata, '$.error_type') as error_type,
                       COUNT(*) as count
                FROM search_index
                {where_clause}
                AND JSON_EXTRACT_STRING(search_metadata, '$.error_type') IS NOT NULL
                GROUP BY error_type
                ORDER BY count DESC
            """
        else:
            return {"error": f"Unknown metric type: {metric_type}"}

        if not self.reflection_db.conn:
            return {
                "error": f"Database connection not available for metric type: {metric_type}"
            }

        results = self.reflection_db.conn.execute(sql, params).fetchall()

        return {
            "metric_type": metric_type,
            "timeframe": timeframe,
            "data": [{"key": row[0], "value": row[1]} for row in results]
            if results
            else [],
        }

    async def _ensure_search_index(self) -> None:
        """Ensure search index is up to date."""
        # Check when index was last updated
        last_update = await self._get_last_index_update()

        # Update if older than 1 hour or if never updated
        if not last_update or (datetime.now(UTC) - last_update).total_seconds() > 3600:
            await self._rebuild_search_index()

    async def _get_last_index_update(self) -> datetime | None:
        """Get timestamp of last index update."""
        sql = "SELECT MAX(last_indexed) FROM search_index"

        if not self.reflection_db.conn:
            return None

        result = self.reflection_db.conn.execute(sql).fetchone()

        if result and result[0]:
            dt = result[0]
            # Ensure datetime is timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        return None

    async def _rebuild_search_index(self) -> None:
        """Rebuild the search index from conversations and reflections."""
        # Index conversations
        await self._index_conversations()

        # Index reflections
        await self._index_reflections()

        # Update facets
        await self._update_search_facets()

    async def _index_conversations(self) -> None:
        """Index all conversations for search."""
        if not self.reflection_db.conn:
            return

        sql = "SELECT id, content, project, timestamp, metadata FROM conversations"
        results = self.reflection_db.conn.execute(sql).fetchall()

        for row in results:
            conv_id, content, project, timestamp, metadata_json = row

            # Extract metadata
            metadata = json.loads(metadata_json) if metadata_json else {}

            # Create indexed content with metadata for better search
            indexed_content = content
            if project:
                indexed_content += f" project:{project}"

            # Extract technical terms and patterns
            tech_terms = self._extract_technical_terms(content)
            if tech_terms:
                indexed_content += " " + " ".join(tech_terms)

            # Create search metadata
            search_metadata = {
                "project": project,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "content_length": len(content),
                "technical_terms": tech_terms,
                **metadata,
            }

            # Insert or update search index
            if self.reflection_db.conn:
                self.reflection_db.conn.execute(
                    """
                    INSERT INTO search_index
                    (id, content_type, content_id, indexed_content, search_metadata, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                    content_type = EXCLUDED.content_type,
                    content_id = EXCLUDED.content_id,
                    indexed_content = EXCLUDED.indexed_content,
                    search_metadata = EXCLUDED.search_metadata,
                    last_indexed = EXCLUDED.last_indexed
                    """,
                    [
                        f"conv_{conv_id}",
                        "conversation",
                        conv_id,
                        indexed_content,
                        json.dumps(search_metadata),
                        datetime.now(UTC),
                    ],
                )

        if self.reflection_db.conn:
            self.reflection_db.conn.commit()

    async def _index_reflections(self) -> None:
        """Index all reflections for search."""
        if not self.reflection_db.conn:
            return

        sql = "SELECT id, content, tags, timestamp, metadata FROM reflections"
        results = self.reflection_db.conn.execute(sql).fetchall()

        for row in results:
            refl_id, content, tags, timestamp, metadata_json = row

            # Extract metadata
            metadata = json.loads(metadata_json) if metadata_json else {}

            # Create indexed content
            indexed_content = content
            if tags:
                indexed_content += " " + " ".join(f"tag:{tag}" for tag in tags)

            # Create search metadata
            search_metadata = {
                "tags": tags or [],
                "timestamp": timestamp.isoformat() if timestamp else None,
                "content_length": len(content),
                **metadata,
            }

            # Insert or update search index
            if self.reflection_db.conn:
                self.reflection_db.conn.execute(
                    """
                    INSERT INTO search_index
                    (id, content_type, content_id, indexed_content, search_metadata, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                    content_type = EXCLUDED.content_type,
                    content_id = EXCLUDED.content_id,
                    indexed_content = EXCLUDED.indexed_content,
                    search_metadata = EXCLUDED.search_metadata,
                    last_indexed = EXCLUDED.last_indexed
                    """,
                    [
                        f"refl_{refl_id}",
                        "reflection",
                        refl_id,
                        indexed_content,
                        json.dumps(search_metadata),
                        datetime.now(UTC),
                    ],
                )

        if self.reflection_db.conn:
            self.reflection_db.conn.commit()

    async def _update_search_facets(self) -> None:
        """Update search facets based on indexed content."""
        if not self.reflection_db.conn:
            return

        # Clear existing facets
        self.reflection_db.conn.execute("DELETE FROM search_facets")

        # Generate facets from search metadata
        facet_queries = {
            "project": "JSON_EXTRACT_STRING(search_metadata, '$.project')",
            "content_type": "content_type",
            "tags": "JSON_EXTRACT_STRING(search_metadata, '$.tags')",
            "technical_terms": "JSON_EXTRACT_STRING(search_metadata, '$.technical_terms')",
        }

        for facet_name, facet_expr in facet_queries.items():
            sql = f"""
                SELECT {facet_expr} as facet_value, COUNT(*) as count
                FROM search_index
                WHERE {facet_expr} IS NOT NULL
                GROUP BY facet_value
                ORDER BY count DESC
            """

            if not self.reflection_db.conn:
                continue

            results = self.reflection_db.conn.execute(sql).fetchall()

            for facet_value, _count in results:
                if isinstance(facet_value, str) and facet_value:
                    facet_id = hashlib.md5(
                        f"{facet_name}_{facet_value}".encode(),
                    ).hexdigest()

                    if self.reflection_db.conn:
                        self.reflection_db.conn.execute(
                            """
                            INSERT INTO search_facets
                            (id, content_type, content_id, facet_name, facet_value, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT (id) DO UPDATE SET
                            content_type = EXCLUDED.content_type,
                            content_id = EXCLUDED.content_id,
                            facet_name = EXCLUDED.facet_name,
                            facet_value = EXCLUDED.facet_value,
                            created_at = EXCLUDED.created_at
                            """,
                            [
                                facet_id,
                                "search_facet",
                                f"{facet_name}_{facet_value}",
                                facet_name,
                                facet_value,
                                datetime.now(UTC).isoformat(),
                            ],
                        )

        if self.reflection_db.conn:
            self.reflection_db.conn.commit()

    def _extract_technical_terms(self, content: str) -> list[str]:
        """Extract technical terms and patterns from content."""
        terms = []

        # Programming language detection
        lang_pattern_names = [
            "python_code",
            "javascript_code",
            "sql_code",
            "error_keywords",
        ]
        lang_mapping = {
            "python_code": "python",
            "javascript_code": "javascript",
            "sql_code": "sql",
            "error_keywords": "error",
        }

        for pattern_name in lang_pattern_names:
            pattern = SAFE_PATTERNS[pattern_name]
            if pattern.search(content):
                terms.append(lang_mapping[pattern_name])

        # Extract function names
        func_pattern = SAFE_PATTERNS["function_definition"]
        func_matches = func_pattern.findall(content)
        terms.extend([f"function:{func}" for func in func_matches[:5]])  # Limit to 5

        # Extract class names
        class_pattern = SAFE_PATTERNS["class_definition"]
        class_matches = class_pattern.findall(content)
        terms.extend([f"class:{cls}" for cls in class_matches[:5]])

        # Extract file extensions
        ext_pattern = SAFE_PATTERNS["file_extension"]
        file_matches = ext_pattern.findall(content)
        terms.extend([f"filetype:{ext}" for ext in set(file_matches[:10])])

        return terms[:20]  # Limit total terms

    def _build_search_query(
        self,
        query: str,
        filters: list[SearchFilter] | None,
    ) -> str:
        """Build search query with filters."""
        # For now, return simple query - could be enhanced with query parsing
        return query

    def _build_filter_conditions(
        self,
        filters: list[SearchFilter],
    ) -> tuple[list[str], list[str | int | datetime]]:
        """Build SQL conditions from filters."""
        conditions = []
        params = []

        for filt in filters:
            if filt.field == "timestamp" and filt.operator == "range":
                start_time, end_time = filt.value
                condition = "last_indexed BETWEEN ? AND ?"
                conditions.append(f"{'NOT ' if filt.negate else ''}{condition}")
                params.extend([start_time, end_time])

            elif filt.operator == "eq":
                condition = (
                    f"JSON_EXTRACT_STRING(search_metadata, '$.{filt.field}') = ?"
                )
                conditions.append(f"{'NOT ' if filt.negate else ''}{condition}")
                params.append(filt.value)

            elif filt.operator == "contains":
                condition = "indexed_content LIKE ?"
                conditions.append(f"{'NOT ' if filt.negate else ''}{condition}")
                params.append(f"%{filt.value}%")

        return conditions, params

    async def _execute_search(
        self,
        query: str,
        sort_by: str,
        limit: int,
        offset: int,
        filters: list[SearchFilter] | None = None,
        content_type: str | None = None,
        timeframe: str | None = None,
    ) -> list[SearchResult]:
        """Execute the actual search."""
        # Start building the SQL query
        sql = """
            SELECT content_id, content_type, indexed_content, search_metadata, last_indexed
            FROM search_index
            WHERE indexed_content LIKE ?
        """
        params: list[str] = [f"%{query}%"]

        # Add content type filter if specified
        if content_type:
            sql += " AND content_type = ?"
            params.append(content_type)

            # Add timeframe filter if specified
            if timeframe:
                # Parse timeframe (e.g., "1d", "7d", "30d")
                if timeframe.endswith("d"):
                    days = int(timeframe[:-1])
                    cutoff_date = datetime.now(UTC) - timedelta(days=days)
                    sql += " AND last_indexed >= ?"
                    params.append(cutoff_date.isoformat())
                elif timeframe.endswith("h"):
                    hours = int(timeframe[:-1])
                    cutoff_date = datetime.now(UTC) - timedelta(hours=hours)
                    sql += " AND last_indexed >= ?"
                    params.append(cutoff_date.isoformat())

        # Add filter conditions if provided
        if filters:
            filter_conditions, filter_params = self._build_filter_conditions(filters)
            if filter_conditions:
                sql += " AND " + " AND ".join(filter_conditions)
                # Convert filter params to strings for SQL execution
                for param in filter_params:
                    if isinstance(param, datetime):
                        params.append(param.isoformat())
                    else:
                        params.append(str(param))

        # Add sorting
        if sort_by == "date":
            sql += " ORDER BY last_indexed DESC"
        elif sort_by == "project":
            sql += " ORDER BY JSON_EXTRACT_STRING(search_metadata, '$.project')"
        else:  # relevance - simple for now
            sql += " ORDER BY LENGTH(indexed_content) DESC"  # Longer content = more relevant

        sql += " LIMIT ? OFFSET ?"
        params.append(str(limit))
        params.append(str(offset))

        if not self.reflection_db.conn:
            return []

        results = self.reflection_db.conn.execute(
            sql,
            [
                param.isoformat() if isinstance(param, datetime) else param
                for param in params
            ],
        ).fetchall()

        search_results = []
        for row in results:
            (
                content_id,
                content_type,
                indexed_content,
                search_metadata_json,
                last_indexed,
            ) = row

            metadata = json.loads(search_metadata_json) if search_metadata_json else {}

            search_results.append(
                SearchResult(
                    content_id=content_id,
                    content_type=content_type or "unknown",
                    title=f"{(content_type or 'unknown').title()} from {metadata.get('project', 'Unknown')}",
                    content=indexed_content[:500] + "..."
                    if len(indexed_content) > 500
                    else indexed_content,
                    score=0.8,  # Simple scoring for now
                    project=metadata.get("project"),
                    timestamp=last_indexed.replace(tzinfo=UTC)
                    if last_indexed.tzinfo is None
                    else last_indexed,
                    metadata=metadata,
                ),
            )

        return search_results

    async def _add_highlights(
        self,
        results: list[SearchResult],
        query: str,
    ) -> list[SearchResult]:
        """Add search highlights to results."""
        query_terms = query.lower().split()

        for result in results:
            highlights = []
            content_lower = result.content.lower()

            for term in query_terms:
                if term in content_lower:
                    # Find context around the term
                    start_pos = content_lower.find(term)
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(result.content), start_pos + len(term) + 50)

                    highlight = result.content[context_start:context_end]
                    highlight = highlight.replace(term, f"<mark>{term}</mark>")
                    highlights.append(highlight)

            result.highlights = highlights[:3]  # Limit to 3 highlights

        return results

    async def _calculate_facets(
        self,
        query: str,
        filters: list[SearchFilter] | None,
        requested_facets: list[str],
    ) -> dict[str, SearchFacet]:
        """Calculate facet counts for search results."""
        facets = {}

        for facet_name in requested_facets:
            if facet_name in self.facet_configs:
                facet_config = self.facet_configs[facet_name]

                sql = """
                    SELECT facet_value, COUNT(*) as count
                    FROM search_facets sf
                    JOIN search_index si ON sf.content_id = si.id
                    WHERE sf.facet_name = ? AND si.indexed_content LIKE ?
                    GROUP BY facet_value
                    ORDER BY count DESC
                    LIMIT ?
                """

                if not self.reflection_db.conn:
                    continue

                results = self.reflection_db.conn.execute(
                    sql,
                    [facet_name, f"%{query}%", facet_config["size"]],
                ).fetchall()

                facets[facet_name] = SearchFacet(
                    name=facet_name,
                    values=[
                        (str(row[0]) if row[0] is not None else "", row[1])
                        for row in results
                    ],
                    facet_type=str(facet_config["type"]),
                )

        return facets

    def _parse_timeframe(self, timeframe: str) -> tuple[datetime, datetime]:
        """Parse timeframe string into start and end times."""
        now = datetime.now(UTC)

        if timeframe == "1h":
            start_time = now - timedelta(hours=1)
        elif timeframe == "1d":
            start_time = now - timedelta(days=1)
        elif timeframe == "1w":
            start_time = now - timedelta(weeks=1)
        elif timeframe == "1m":
            start_time = now - timedelta(days=30)
        elif timeframe == "1y":
            start_time = now - timedelta(days=365)
        else:
            # Try to parse as ISO date range or default to 30 days
            start_time = now - timedelta(days=30)

        return start_time, now

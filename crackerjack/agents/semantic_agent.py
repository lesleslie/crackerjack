"""Semantic search and context analysis agent for code pattern discovery and semantic improvements."""

import typing as t
from pathlib import Path

from ..models.semantic_models import SearchQuery, SemanticConfig
from ..services.vector_store import VectorStore
from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class SemanticAgent(SubAgent):
    """AI agent specialized in semantic search and code context analysis.

    This agent enhances code understanding by providing semantic context,
    finding similar code patterns, and suggesting improvements based on
    codebase-wide analysis using vector embeddings.
    """

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.semantic_insights: dict[str, t.Any] = {}
        self.pattern_stats: dict[str, int] = {
            "patterns_discovered": 0,
            "context_enhancements": 0,
            "semantic_suggestions": 0,
            "similar_patterns_found": 0,
        }

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.SEMANTIC_CONTEXT}

    async def can_handle(self, issue: Issue) -> float:
        """Determine confidence level for handling semantic context issues."""
        if issue.type != IssueType.SEMANTIC_CONTEXT:
            return 0.0

        confidence = 0.8
        message_lower = issue.message.lower()

        # Higher confidence for semantic-specific terms
        if any(
            pattern in message_lower
            for pattern in (
                "semantic",
                "context",
                "pattern",
                "similarity",
                "related code",
                "code understanding",
                "similar implementation",
            )
        ):
            confidence = 0.85

        return confidence

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Analyze code using semantic search and provide contextual insights."""
        self.log(f"Analyzing semantic context issue: {issue.message}")

        validation_result = self._validate_semantic_issue(issue)
        if validation_result:
            return validation_result

        if issue.file_path is None:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path provided for semantic analysis"],
            )

        file_path = Path(issue.file_path)

        try:
            # Initialize semantic services
            config = self._create_semantic_config()
            vector_store = self._get_vector_store(config)

            # Perform semantic analysis
            result = await self._perform_semantic_analysis(
                file_path, vector_store, issue
            )

            # Update stats
            self._update_pattern_stats(result)

            return result

        except Exception as e:
            return self._create_semantic_error_result(e)

    @staticmethod
    def _validate_semantic_issue(issue: Issue) -> FixResult | None:
        """Validate that the semantic issue can be processed."""
        if not issue.file_path:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No file path specified for semantic analysis"],
            )

        file_path = Path(issue.file_path)
        if not file_path.exists():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"File not found: {file_path}"],
            )

        return None

    @staticmethod
    def _create_semantic_config() -> SemanticConfig:
        """Create semantic search configuration."""
        return SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

    def _get_vector_store(self, config: SemanticConfig) -> VectorStore:
        """Get vector store instance with persistent database."""
        db_path = self._get_persistent_db_path()
        return VectorStore(config, db_path=db_path)

    def _get_persistent_db_path(self) -> Path:
        """Get the path to the persistent semantic search database."""
        db_path = self.context.project_path / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        return db_path

    async def _perform_semantic_analysis(
        self, file_path: Path, vector_store: VectorStore, issue: Issue
    ) -> FixResult:
        """Perform comprehensive semantic analysis of the code file."""
        # Read file content
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        # Index the file if not already indexed
        try:
            embeddings = vector_store.index_file(file_path)
            self.log(f"Indexed {len(embeddings)} chunks from {file_path.name}")
        except Exception as e:
            self.log(f"Warning: Could not index file {file_path}: {e}")

        # Perform semantic search for related patterns
        semantic_insights = await self._discover_semantic_patterns(
            vector_store, file_path, content, issue
        )

        # Generate recommendations based on semantic analysis
        recommendations = self._generate_semantic_recommendations(semantic_insights)

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[
                f"Semantic analysis completed for {file_path.name}",
                f"Discovered {len(semantic_insights.get('related_patterns', []))} related patterns",
                f"Generated {len(recommendations)} semantic recommendations",
            ],
            recommendations=recommendations,
            files_modified=[],  # Semantic agent provides insights, doesn't modify files
        )

    async def _discover_semantic_patterns(
        self,
        vector_store: VectorStore,
        file_path: Path,
        content: str,
        issue: Issue,
    ) -> dict[str, t.Any]:
        """Discover semantic patterns and related code through vector search."""
        insights: dict[str, t.Any] = {
            "related_patterns": [],
            "similar_functions": [],
            "context_suggestions": [],
            "pattern_clusters": [],
        }

        # Extract key functions and classes for semantic analysis
        code_elements = self._extract_code_elements(content)

        for element in code_elements:
            # Search for similar patterns
            search_query = SearchQuery(
                query=element["signature"],
                max_results=5,
                min_similarity=0.6,
                file_types=["py"],
            )

            try:
                results = vector_store.search(search_query)
                if results:
                    # Filter out results from the same file
                    related_results = [
                        result for result in results if result.file_path != file_path
                    ]

                    if related_results:
                        insights["related_patterns"].append(
                            {
                                "element": element,
                                "related_code": [
                                    {
                                        "file_path": str(result.file_path),
                                        "content": result.content[
                                            :200
                                        ],  # Truncate for readability
                                        "similarity_score": result.similarity_score,
                                        "lines": f"{result.start_line}-{result.end_line}",
                                    }
                                    for result in related_results[:3]  # Top 3 matches
                                ],
                            }
                        )

            except Exception as e:
                self.log(f"Warning: Semantic search failed for {element['name']}: {e}")

        # Analyze issue-specific context
        if issue.message:
            issue_insights = await self._analyze_issue_context(vector_store, issue)
            insights["context_suggestions"].extend(issue_insights)

        return insights

    def _extract_docstring_from_node(self, node: t.Any) -> str:
        """Extract docstring from AST node, handling both old and new formats."""
        import ast

        if not node.body or not isinstance(node.body[0], ast.Expr):
            return ""

        value = node.body[0].value
        if hasattr(value, "s"):  # Old ast.Str format
            return str(value.s)[:100]
        elif hasattr(value, "value") and isinstance(
            value.value, str
        ):  # New ast.Constant format
            return str(value.value)[:100]
        return ""

    def _build_function_signature(self, node: t.Any) -> str:
        """Build function signature from AST FunctionDef node."""
        signature = f"def {node.name}("
        if node.args.args:
            args = [arg.arg for arg in node.args.args[:3]]  # First 3 args
            signature += ", ".join(args)
        signature += ")"
        return signature

    def _build_class_signature(self, node: t.Any) -> str:
        """Build class signature from AST ClassDef node."""
        signature = f"class {node.name}"
        if node.bases:
            bases = [self._get_ast_name(base) for base in node.bases[:2]]
            signature += f"({', '.join(bases)})"
        return signature

    def _get_ast_name(self, node: t.Any) -> str:
        """Get name from AST node."""
        import ast

        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_ast_name(node.value)}.{node.attr}"
        return "Unknown"

    def _extract_ast_elements(self, content: str) -> list[dict[str, t.Any]]:
        """Extract code elements using AST parsing."""
        import ast

        class CodeElementExtractor(ast.NodeVisitor):
            def __init__(self, parent: "SemanticAgent") -> None:
                self.elements: list[dict[str, t.Any]] = []
                self.parent = parent

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.elements.append(
                    {
                        "type": "function",
                        "name": node.name,
                        "signature": self.parent._build_function_signature(node),
                        "docstring": self.parent._extract_docstring_from_node(node),
                        "line_number": node.lineno,
                    }
                )
                self.generic_visit(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.elements.append(
                    {
                        "type": "class",
                        "name": node.name,
                        "signature": self.parent._build_class_signature(node),
                        "line_number": node.lineno,
                    }
                )
                self.generic_visit(node)

        tree = ast.parse(content)
        extractor = CodeElementExtractor(self)
        extractor.visit(tree)
        return extractor.elements[:10]  # Limit to top 10 elements

    def _extract_text_elements(self, content: str) -> list[dict[str, t.Any]]:
        """Extract code elements using simple text patterns."""
        elements = []
        lines = content.split("\n")
        for i, line in enumerate(lines[:50]):  # Check first 50 lines
            stripped = line.strip()
            if stripped.startswith("def ") and "(" in stripped:
                func_name = stripped.split("(")[0].replace("def ", "").strip()
                elements.append(
                    {
                        "type": "function",
                        "name": func_name,
                        "signature": stripped,
                        "line_number": i + 1,
                    }
                )
            elif stripped.startswith("class ") and ":" in stripped:
                class_name = stripped.split(":")[0].replace("class ", "").strip()
                elements.append(
                    {
                        "type": "class",
                        "name": class_name,
                        "signature": stripped,
                        "line_number": i + 1,
                    }
                )
        return elements

    def _extract_code_elements(self, content: str) -> list[dict[str, t.Any]]:
        """Extract key code elements for semantic analysis."""
        try:
            return self._extract_ast_elements(content)
        except SyntaxError:
            return self._extract_text_elements(content)

    async def _analyze_issue_context(
        self, vector_store: VectorStore, issue: Issue
    ) -> list[dict[str, t.Any]]:
        """Analyze the specific issue context using semantic search."""
        suggestions = []

        # Search for similar issues or patterns
        search_query = SearchQuery(
            query=issue.message,
            max_results=5,
            min_similarity=0.5,
        )

        try:
            results = vector_store.search(search_query)
            if results:
                suggestions.append(
                    {
                        "type": "similar_issues",
                        "description": f"Found {len(results)} similar patterns in codebase",
                        "examples": [
                            {
                                "file": str(result.file_path.name),
                                "content": result.content[:150],
                                "similarity": result.similarity_score,
                            }
                            for result in results[:3]
                        ],
                    }
                )
        except Exception as e:
            self.log(f"Warning: Issue context analysis failed: {e}")

        return suggestions

    def _generate_semantic_recommendations(
        self, insights: dict[str, t.Any]
    ) -> list[str]:
        """Generate actionable recommendations based on semantic analysis."""
        recommendations = []

        related_patterns = insights.get("related_patterns", [])
        context_suggestions = insights.get("context_suggestions", [])

        if related_patterns:
            recommendations.append(
                f"Found {len(related_patterns)} similar code patterns across the codebase"
            )

            # Analyze pattern consistency
            high_similarity_count = sum(
                1
                for pattern in related_patterns
                for code in pattern["related_code"]
                if code["similarity_score"] > 0.8
            )

            if high_similarity_count > 0:
                recommendations.append(
                    f"Detected {high_similarity_count} highly similar implementations - "
                    "consider refactoring for DRY principle compliance"
                )

        if context_suggestions:
            recommendations.append(
                "Semantic analysis revealed contextual insights for code understanding"
            )

        # General semantic recommendations
        recommendations.extend(
            [
                "Consider semantic indexing of related modules for better code discovery",
                "Review similar patterns for consistency in naming and implementation",
                "Use semantic search to discover reusable components before implementing new ones",
            ]
        )

        return recommendations

    def _update_pattern_stats(self, result: FixResult) -> None:
        """Update pattern discovery statistics."""
        if result.success:
            self.pattern_stats["patterns_discovered"] += len(result.fixes_applied)
            self.pattern_stats["semantic_suggestions"] += len(result.recommendations)

    @staticmethod
    def _create_semantic_error_result(error: Exception) -> FixResult:
        """Create error result for semantic analysis failures."""
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Semantic analysis failed: {error}"],
            recommendations=[
                "Ensure semantic search index is properly initialized",
                "Check if file contains valid code for analysis",
                "Verify semantic search configuration is correct",
            ],
        )

    async def plan_before_action(self, issue: Issue) -> dict[str, t.Any]:
        """Plan semantic analysis strategy before execution."""
        return {
            "strategy": "semantic_context_analysis",
            "confidence": 0.8,
            "approach": [
                "Index file content for semantic search",
                "Discover related code patterns using vector embeddings",
                "Analyze semantic similarity across codebase",
                "Generate contextual recommendations",
            ],
            "expected_insights": [
                "Similar code patterns and implementations",
                "Opportunities for code reuse and refactoring",
                "Contextual understanding of code relationships",
            ],
        }


# Register the agent with the agent registry
agent_registry.register(SemanticAgent)

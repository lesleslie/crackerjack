"""CLI handlers for semantic search operations."""

from pathlib import Path
from textwrap import dedent

from rich.console import Console

console = Console()

from rich.panel import Panel
from rich.table import Table

from crackerjack.models.semantic_models import SearchQuery, SemanticConfig
from crackerjack.services.vector_store import VectorStore


def handle_semantic_index(file_path: str) -> None:
    """Handle indexing a file for semantic search.

    Args:
        file_path: Path to the file or directory to index
    """
    try:
        console.print(f"[cyan]Indexing file for semantic search:[/cyan] {file_path}")

        # Validate path
        path_obj = Path(file_path)
        if not path_obj.exists():
            console.print(f"[red]Error:[/red] File does not exist: {file_path}")
            return

        # Create default configuration
        config = SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

        # Initialize vector store with persistent database
        db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        vector_store = VectorStore(config, db_path=db_path)

        if path_obj.is_file():
            # Index single file
            embeddings = vector_store.index_file(path_obj)
            console.print(
                f"[green]✅ Successfully indexed {len(embeddings)} chunks from {path_obj.name}[/green]"
            )
        else:
            # Index directory (recursively)
            total_files = 0
            total_chunks = 0

            for file in path_obj.rglob("*.py"):  # Index Python files
                try:
                    embeddings = vector_store.index_file(file)
                    total_files += 1
                    total_chunks += len(embeddings)
                    console.print(
                        f"[dim]Indexed {len(embeddings)} chunks from {file.relative_to(path_obj)}[/dim]"
                    )
                except Exception as e:
                    console.print(
                        f"[yellow]Warning:[/yellow] Failed to index {file}: {e}"
                    )

            console.print(
                f"[green]✅ Successfully indexed {total_files} files with {total_chunks} total chunks[/green]"
            )

        # Show index stats
        stats = vector_store.get_stats()
        console.print(
            f"[cyan]Index now contains:[/cyan] {stats.total_files} files, {stats.total_chunks} chunks"
        )

    except Exception as e:
        console.print(
            f"[red]Error indexing file:[/red] {str(e).replace('[', '\\[').replace(']', '\\]')}"
        )


def handle_semantic_search(query: str) -> None:
    """Handle semantic search across indexed files.

    Args:
        query: The search query text
    """
    try:
        console.print(f"[cyan]Performing semantic search for:[/cyan] {query}")

        # Create default configuration
        config = SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

        # Create search query
        search_query = SearchQuery(
            query=query,
            max_results=10,
            min_similarity=0.3,  # Lower threshold for CLI to show more results
        )

        # Initialize vector store with persistent database
        db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        vector_store = VectorStore(config, db_path=db_path)
        results = vector_store.search(search_query)

        if not results:
            console.print(
                "[yellow]No results found. Try a different search term or index more files.[/yellow]"
            )
            return

        # Display results in a table
        table = Table(title=f"Semantic Search Results for: '{query}'")
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Lines", style="magenta", justify="center")
        table.add_column("Score", style="green", justify="center")
        table.add_column("Content Preview", style="white")

        for result in results:
            # Truncate content for display
            content_preview = (
                result.content[:80] + "..."
                if len(result.content) > 80
                else result.content
            )
            content_preview = content_preview.replace("\n", " ").strip()

            # Escape Rich markup in content to prevent rendering issues
            content_preview = content_preview.replace("[", "\\[").replace("]", "\\]")

            table.add_row(
                str(result.file_path.name),
                f"{result.start_line}-{result.end_line}",
                f"{result.similarity_score:.3f}",
                content_preview,
            )

        console.print(
            Panel(table, title="Semantic Search Results", border_style="cyan")
        )

        # Show detailed content for top result
        if results:
            top_result = results[0]
            # Escape Rich markup in the detailed content
            escaped_content = (
                top_result.content.strip().replace("[", "\\[").replace("]", "\\]")
            )
            console.print(
                Panel(
                    dedent(f"""
                [cyan]Top Result Details:[/cyan]
                [bold]File:[/bold] {top_result.file_path}
                [bold]Lines:[/bold] {top_result.start_line}-{top_result.end_line}
                [bold]Similarity Score:[/bold] {top_result.similarity_score:.4f}

                [bold]Content:[/bold]
                {escaped_content}
                """).strip(),
                    title="🎯 Best Match",
                    border_style="green",
                )
            )

    except Exception as e:
        console.print(
            f"[red]Error performing search:[/red] {str(e).replace('[', '\\[').replace(']', '\\]')}"
        )


def handle_semantic_stats() -> None:
    """Handle displaying semantic search index statistics."""
    try:
        console.print("[cyan]Retrieving semantic search index statistics...[/cyan]")

        # Create default configuration
        config = SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

        # Initialize vector store with persistent database
        db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        vector_store = VectorStore(config, db_path=db_path)
        stats = vector_store.get_stats()

        # Create stats table
        table = Table(title="Semantic Search Index Statistics")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Total Files", str(stats.total_files))
        table.add_row("Total Chunks", str(stats.total_chunks))
        table.add_row("Index Size", f"{stats.index_size_mb:.2f} MB")

        # Calculate average chunks per file
        avg_chunks = (
            stats.total_chunks / stats.total_files if stats.total_files > 0 else 0.0
        )
        table.add_row("Average Chunks per File", f"{avg_chunks:.1f}")

        table.add_row("Embedding Model", config.embedding_model)
        table.add_row("Embedding Dimension", "384")  # ONNX fallback uses 384 dimensions

        if stats.last_updated:
            table.add_row(
                "Last Updated", stats.last_updated.strftime("%Y-%m-%d %H:%M:%S")
            )

        console.print(Panel(table, border_style="cyan"))

        if stats.total_files == 0:
            console.print(
                Panel(
                    "[yellow]The semantic search index is empty. Use [bold]--index[/bold] to add files.[/yellow]",
                    title="💡 Tip",
                    border_style="yellow",
                )
            )

    except Exception as e:
        console.print(
            f"[red]Error retrieving stats:[/red] {str(e).replace('[', '\\[').replace(']', '\\]')}"
        )


def handle_remove_from_semantic_index(file_path: str) -> None:
    """Handle removing a file from the semantic search index.

    Args:
        file_path: Path to the file to remove
    """
    try:
        console.print(
            f"[cyan]Removing file from semantic search index:[/cyan] {file_path}"
        )

        # Validate path
        path_obj = Path(file_path)

        # Create default configuration
        config = SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

        # Initialize vector store with persistent database
        db_path = Path.cwd() / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        vector_store = VectorStore(config, db_path=db_path)
        success = vector_store.remove_file(path_obj)

        if success:
            console.print(
                f"[green]✅ Successfully removed {path_obj.name} from index[/green]"
            )
        else:
            console.print(
                f"[yellow]Warning:[/yellow] File {path_obj.name} was not found in index"
            )

        # Show updated stats
        stats = vector_store.get_stats()
        console.print(
            f"[cyan]Index now contains:[/cyan] {stats.total_files} files, {stats.total_chunks} chunks"
        )

    except Exception as e:
        console.print(
            f"[red]Error removing file:[/red] {str(e).replace('[', '\\[').replace(']', '\\]')}"
        )

import typing as t

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from crackerjack.services.cache import CrackerjackCache


def handle_clear_cache() -> None:
    """Clear all caches and display results."""
    try:
        cache = CrackerjackCache()

        # Clear memory caches and get cleanup stats
        cleanup_results = cache.cleanup_all()

        # Note:CrackerjackCache uses memory-only caching (no disk cache to clear)

        # Calculate total items cleared
        total_cleared = sum(cleanup_results.values())

        # Create results table
        table = Table(
            title="Cache Cleared", show_header=True, header_style="bold green"
        )
        table.add_column("Cache Type", style="cyan", no_wrap=True)
        table.add_column("Items Cleared", justify="right", style="yellow")

        for cache_type, count in cleanup_results.items():
            table.add_row(cache_type.replace("_", " ").title(), str(count))

        table.add_row("", "", end_section=True)
        table.add_row("Total", str(total_cleared), style="bold green")

        console.print()
        console.print(Panel(table, title="Cache Cleared", border_style="green"))
        console.print(f"\n✅ Successfully cleared {total_cleared} cache entries")

    except Exception as e:
        console.print(f"\n❌ Error clearing cache: {e}", style="bold red")


def handle_cache_stats() -> None:
    """Display detailed cache statistics."""
    try:
        cache = CrackerjackCache()
        stats = cache.get_cache_stats()

        main_table = _create_cache_stats_table()
        totals = _populate_cache_stats_table(main_table, stats)
        _add_cache_totals_row(main_table, totals)

        console.print()
        console.print(Panel(main_table, border_style="blue"))

        _display_performance_insights(totals)
        _display_cache_directory_info(cache)

    except Exception as e:
        console.print(f"\n❌ Error retrieving cache stats: {e}", style="bold red")


def _create_cache_stats_table() -> Table:
    """Create and configure the main cache statistics table."""
    table = Table(title="Cache Statistics", show_header=True, header_style="bold blue")
    table.add_column("Cache Layer", style="cyan", no_wrap=True)
    table.add_column("Hit Rate %", justify="right", style="green")
    table.add_column("Hits", justify="right", style="yellow")
    table.add_column("Misses", justify="right", style="red")
    table.add_column("Entries", justify="right", style="magenta")
    table.add_column("Size (MB)", justify="right", style="blue")
    return table


def _populate_cache_stats_table(
    table: Table, stats: dict[str, t.Any]
) -> dict[str, t.Any]:
    """Populate table with cache statistics and return totals."""
    totals = {"hits": 0, "misses": 0, "entries": 0, "size": 0.0}

    for cache_name, cache_stats in stats.items():
        hit_rate = cache_stats.get("hit_rate_percent", 0.0)
        hits = cache_stats.get("hits", 0)
        misses = cache_stats.get("misses", 0)
        entries = cache_stats.get("total_entries", 0)
        size_mb = cache_stats.get("total_size_mb", 0.0)

        hit_rate_style = _get_hit_rate_style(hit_rate)

        table.add_row(
            cache_name.replace("_", " ").title(),
            Text(f"{hit_rate:.1f}", style=hit_rate_style),
            str(hits),
            str(misses),
            str(entries),
            f"{size_mb:.2f}",
        )

        totals["hits"] += hits
        totals["misses"] += misses
        totals["entries"] += entries
        totals["size"] += size_mb

    return totals


def _get_hit_rate_style(hit_rate: float) -> str:
    """Get color style for hit rate based on performance."""
    return "green" if hit_rate > 70 else "yellow" if hit_rate > 40 else "red"


def _add_cache_totals_row(table: Table, totals: dict[str, t.Any]) -> None:
    """Add totals row to cache statistics table."""
    overall_hit_rate = (
        (totals["hits"] / (totals["hits"] + totals["misses"]) * 100)
        if (totals["hits"] + totals["misses"]) > 0
        else 0
    )
    overall_style = _get_hit_rate_style(overall_hit_rate)

    table.add_row("", "", "", "", "", "", end_section=True)
    table.add_row(
        "Overall",
        Text(f"{overall_hit_rate:.1f}", style=f"bold {overall_style}"),
        str(totals["hits"]),
        str(totals["misses"]),
        str(totals["entries"]),
        f"{totals['size']:.2f}",
        style="bold",
    )


def _display_performance_insights(totals: dict[str, t.Any]) -> None:
    """Display performance insights panel based on cache statistics."""
    overall_hit_rate = (
        (totals["hits"] / (totals["hits"] + totals["misses"]) * 100)
        if (totals["hits"] + totals["misses"]) > 0
        else 0
    )

    insights = _generate_performance_insights(overall_hit_rate, totals["size"])

    if insights:
        insights_text = "\n".join(insights)
        insights_panel = Panel(
            insights_text,
            title="Performance Insights",
            border_style="blue",
            padding=(1, 2),
        )
        console.print()
        console.print(insights_panel)


def _generate_performance_insights(hit_rate: float, total_size: float) -> list[str]:
    """Generate performance insights based on cache metrics."""
    insights = []

    if hit_rate > 80:
        insights.append("🚀 Excellent cache performance!")
    elif hit_rate > 60:
        insights.append("✅ Good cache performance")
    elif hit_rate > 30:
        insights.append("⚠️ Moderate cache performance - consider cache warming")
    else:
        insights.append("❌ Poor cache performance - check cache configuration")

    if total_size > 100:
        insights.append(f"💾 Large cache size ({total_size:.1f}MB) - consider cleanup")

    return insights


def _display_cache_directory_info(cache: CrackerjackCache) -> None:
    """Display cache directory information."""
    if not (cache.enable_disk_cache and cache.cache_dir):
        return

    cache_dir_info = f"📁 Cache Directory: {cache.cache_dir}"
    if cache.cache_dir.exists():
        disk_files = len(list(cache.cache_dir.rglob("*.cache")))
        cache_dir_info += f" ({disk_files} files)"

    console.print()
    console.print(cache_dir_info)


def _handle_cache_commands(clear_cache: bool, cache_stats: bool) -> bool:
    """Handle cache management commands. Returns True if a cache command was executed."""
    if clear_cache:
        handle_clear_cache()
        return True

    if cache_stats:
        handle_cache_stats()
        return True

    return False

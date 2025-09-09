import typing as t
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from crackerjack.services.cache import CrackerjackCache


def handle_clear_cache(console: Console) -> None:
    """Clear all caches and display results."""
    try:
        cache = CrackerjackCache()

        # Clear memory caches and get cleanup stats
        cleanup_results = cache.cleanup_all()

        # Clear disk cache completely
        if cache.enable_disk_cache and cache.cache_dir:
            cache.disk_cache.clear()

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
        console.print(table)
        console.print(f"\n✅ Successfully cleared {total_cleared} cache entries")

    except Exception as e:
        console.print(f"\n❌ Error clearing cache: {e}", style="bold red")


def handle_cache_stats(console: Console) -> None:
    """Display detailed cache statistics."""
    try:
        cache = CrackerjackCache()
        stats = cache.get_cache_stats()

        # Create main statistics table
        main_table = Table(
            title="Cache Statistics", show_header=True, header_style="bold blue"
        )
        main_table.add_column("Cache Layer", style="cyan", no_wrap=True)
        main_table.add_column("Hit Rate %", justify="right", style="green")
        main_table.add_column("Hits", justify="right", style="yellow")
        main_table.add_column("Misses", justify="right", style="red")
        main_table.add_column("Entries", justify="right", style="magenta")
        main_table.add_column("Size (MB)", justify="right", style="blue")

        # Add rows for each cache type
        total_hits = 0
        total_misses = 0
        total_entries = 0
        total_size = 0.0

        for cache_name, cache_stats in stats.items():
            hit_rate = cache_stats.get("hit_rate_percent", 0.0)
            hits = cache_stats.get("hits", 0)
            misses = cache_stats.get("misses", 0)
            entries = cache_stats.get("total_entries", 0)
            size_mb = cache_stats.get("total_size_mb", 0.0)

            # Color coding for hit rates
            hit_rate_style = (
                "green" if hit_rate > 70 else "yellow" if hit_rate > 40 else "red"
            )

            main_table.add_row(
                cache_name.replace("_", " ").title(),
                Text(f"{hit_rate:.1f}", style=hit_rate_style),
                str(hits),
                str(misses),
                str(entries),
                f"{size_mb:.2f}",
            )

            total_hits += hits
            total_misses += misses
            total_entries += entries
            total_size += size_mb

        # Add totals row
        overall_hit_rate = (
            (total_hits / (total_hits + total_misses) * 100)
            if (total_hits + total_misses) > 0
            else 0
        )
        overall_style = (
            "green"
            if overall_hit_rate > 70
            else "yellow"
            if overall_hit_rate > 40
            else "red"
        )

        main_table.add_row("", "", "", "", "", "", end_section=True)
        main_table.add_row(
            "Overall",
            Text(f"{overall_hit_rate:.1f}", style=f"bold {overall_style}"),
            str(total_hits),
            str(total_misses),
            str(total_entries),
            f"{total_size:.2f}",
            style="bold",
        )

        # Create performance insights panel
        insights = []
        if overall_hit_rate > 80:
            insights.append("🚀 Excellent cache performance!")
        elif overall_hit_rate > 60:
            insights.append("✅ Good cache performance")
        elif overall_hit_rate > 30:
            insights.append("⚠️ Moderate cache performance - consider cache warming")
        else:
            insights.append("❌ Poor cache performance - check cache configuration")

        if total_size > 100:
            insights.append(
                f"💾 Large cache size ({total_size:.1f}MB) - consider cleanup"
            )

        # Display results
        console.print()
        console.print(main_table)

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

        # Show cache directory info
        if cache.enable_disk_cache and cache.cache_dir:
            cache_dir_info = f"📁 Cache Directory: {cache.cache_dir}"
            if cache.cache_dir.exists():
                disk_files = len(list(cache.cache_dir.rglob("*.cache")))
                cache_dir_info += f" ({disk_files} files)"

            console.print()
            console.print(cache_dir_info)

    except Exception as e:
        console.print(f"\n❌ Error retrieving cache stats: {e}", style="bold red")


def _handle_cache_commands(
    clear_cache: bool, cache_stats: bool, console: Console
) -> bool:
    """Handle cache management commands. Returns True if a cache command was executed."""
    if clear_cache:
        handle_clear_cache(console)
        return True

    if cache_stats:
        handle_cache_stats(console)
        return True

    return False

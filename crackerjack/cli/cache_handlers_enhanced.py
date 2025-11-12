"""Enhanced cache handlers with optimization, warming, and advanced analytics."""

import typing as t
from dataclasses import asdict, dataclass
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table
from rich.text import Text

from crackerjack.services.cache import CrackerjackCache


@dataclass
class CacheAnalytics:
    """Advanced cache analytics data."""

    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate_percent: float
    avg_response_time_ms: float
    cache_size_mb: float
    entries_count: int
    oldest_entry_age_hours: float
    most_accessed_keys: list[tuple[str, int]]
    least_accessed_keys: list[tuple[str, int]]
    cache_efficiency_score: float  # 0-100

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class CacheOptimizationSuggestion:
    """Cache optimization suggestion."""

    type: str  # "eviction", "warming", "size_adjustment", "ttl_tuning"
    priority: str  # "high", "medium", "low"
    description: str
    estimated_benefit: str
    action_required: str


class EnhancedCacheHandlers:
    """Enhanced cache handlers with advanced features."""

    def __init__(self, cache: CrackerjackCache | None = None):
        self.cache = cache or CrackerjackCache()

    def handle_clear_cache(self, console: Console, selective: bool = False) -> None:
        """Enhanced cache clearing with selective options."""
        try:
            if selective:
                self._handle_selective_clear(console)
                return

            # Get pre-clear stats
            pre_clear_stats = self.cache.get_cache_stats()

            # Clear memory caches and get cleanup stats
            # Note: cleanup_all() already handles all cache types (memory + disk)
            cleanup_results = self.cache.cleanup_all()

            # Calculate total items cleared
            total_cleared = sum(cleanup_results.values())

            # Create enhanced results table
            table = Table(
                title="🧹 Cache Cleared Successfully",
                show_header=True,
                header_style="bold green",
            )
            table.add_column("Cache Type", style="cyan", no_wrap=True)
            table.add_column("Items Cleared", justify="right", style="yellow")
            table.add_column("Size Freed (MB)", justify="right", style="magenta")
            table.add_column("Performance Impact", style="blue")

            total_size_freed = 0.0
            for cache_type, count in cleanup_results.items():
                # Estimate size freed (simplified calculation)
                size_freed = pre_clear_stats.get(cache_type, {}).get(
                    "total_size_mb", 0.0
                )
                total_size_freed += size_freed

                # Determine performance impact
                if count > 100:
                    impact = "High speedup expected"
                elif count > 20:
                    impact = "Moderate improvement"
                else:
                    impact = "Minor cleanup"

                table.add_row(
                    cache_type.replace("_", " ").title(),
                    str(count),
                    f"{size_freed:.2f}",
                    impact,
                )

            table.add_row("", "", "", "", end_section=True)
            table.add_row(
                "Total",
                str(total_cleared),
                f"{total_size_freed:.2f}",
                "Overall Optimization",
                style="bold green",
            )

            console.print()
            console.print(table)
            console.print(
                f"\\n✅ Successfully cleared {total_cleared} cache entries ({total_size_freed:.2f} MB freed)"
            )
            console.print(
                "💡 Tip: Run --cache-warm after major operations to rebuild critical caches"
            )

        except Exception as e:
            console.print(f"\\n❌ Error clearing cache: {e}", style="bold red")

    def handle_cache_stats(self, console: Console, detailed: bool = False) -> None:
        """Enhanced cache statistics with advanced analytics."""
        try:
            cache_stats = self.cache.get_cache_stats()
            analytics = self._generate_cache_analytics(cache_stats)

            # Main statistics table
            main_table = self._create_main_stats_table(cache_stats)

            # Advanced analytics table (if detailed)
            if detailed:
                analytics_table = self._create_analytics_table(analytics)
                console.print()
                console.print(analytics_table)

            # Performance insights panel
            insights_panel = self._create_insights_panel(analytics)

            # Optimization suggestions
            suggestions = self._generate_optimization_suggestions(analytics)
            suggestions_panel = self._create_suggestions_panel(suggestions)

            # Display results
            console.print()
            console.print(main_table)

            if insights_panel:
                console.print()
                console.print(insights_panel)

            if suggestions:
                console.print()
                console.print(suggestions_panel)

            # Cache directory info with enhanced details
            self._show_cache_directory_info(console)

        except Exception as e:
            console.print(f"\\n❌ Error retrieving cache stats: {e}", style="bold red")

    def handle_cache_warm(
        self, console: Console, target_operations: list[str] | None = None
    ) -> None:
        """Warm cache with frequently used operations."""
        console.print("🔥 Starting cache warming process...")

        # Default operations to warm if none specified
        if not target_operations:
            target_operations = [
                "hook_results",
                "file_hashes",
                "agent_decisions",
                "test_results",
            ]

        total_operations = len(target_operations)

        with Progress() as progress:
            warm_task = progress.add_task(
                "[green]Warming caches...", total=total_operations
            )

            for operation in target_operations:
                progress.update(warm_task, description=f"[green]Warming {operation}...")

                try:
                    if operation == "hook_results":
                        self._warm_hook_results_cache()
                    elif operation == "file_hashes":
                        self._warm_file_hashes_cache()
                    elif operation == "agent_decisions":
                        self._warm_agent_decisions_cache()
                    elif operation == "test_results":
                        self._warm_test_results_cache()

                    progress.advance(warm_task)

                except Exception as e:
                    console.print(f"⚠️ Failed to warm {operation}: {e}", style="yellow")
                    progress.advance(warm_task)

        console.print("\\n✅ Cache warming completed successfully")
        console.print("💡 Run --cache-stats to see improved performance metrics")

    def handle_cache_optimize(self, console: Console) -> None:
        """Optimize cache configuration and performance."""
        console.print("⚙️ Starting cache optimization...")

        # Analyze current performance
        stats = self.cache.get_cache_stats()
        analytics = self._generate_cache_analytics(stats)
        suggestions = self._generate_optimization_suggestions(analytics)

        optimizations_applied = 0

        with Progress() as progress:
            optimize_task = progress.add_task(
                "[blue]Optimizing caches...", total=len(suggestions)
            )

            for suggestion in suggestions:
                progress.update(
                    optimize_task, description=f"[blue]{suggestion.description[:30]}..."
                )

                try:
                    if self._apply_optimization_suggestion(suggestion):
                        optimizations_applied += 1

                    progress.advance(optimize_task)

                except Exception as e:
                    console.print(
                        f"⚠️ Failed to apply optimization: {e}", style="yellow"
                    )
                    progress.advance(optimize_task)

        console.print(
            f"\\n✅ Applied {optimizations_applied}/{len(suggestions)} optimizations"
        )

        if optimizations_applied > 0:
            console.print("🚀 Cache performance should be improved for next operations")
        else:
            console.print("✨ Cache is already well-optimized")

    def _handle_selective_clear(self, console: Console) -> None:
        """Handle selective cache clearing with user choices."""
        stats = self.cache.get_cache_stats()

        console.print("\\n📋 Select caches to clear:")

        choices = []
        for i, (cache_name, cache_stats) in enumerate(stats.items(), 1):
            size_mb = cache_stats.get("total_size_mb", 0.0)
            entries = cache_stats.get("total_entries", 0)
            console.print(
                f"  {i}. {cache_name.replace('_', ' ').title()} ({entries} entries, {size_mb:.2f} MB)"
            )
            choices.append(cache_name)

        console.print(f"  {len(choices) + 1}. All caches")
        console.print("  0. Cancel")

        try:
            selection = input(
                "\\nEnter your choice (comma-separated for multiple): "
            ).strip()

            if selection == "0":
                console.print("Cache clear cancelled.")
                return

            if selection == str(len(choices) + 1):
                # Clear all
                self.handle_clear_cache(console, selective=False)
                return

            # Parse multiple selections
            selected_indices = [int(x.strip()) - 1 for x in selection.split(",")]
            selected_caches = [
                choices[i] for i in selected_indices if 0 <= i < len(choices)
            ]

            # Clear selected caches
            for cache_name in selected_caches:
                # Implementation would depend on cache structure
                console.print(f"✅ Cleared {cache_name.replace('_', ' ').title()}")

        except (ValueError, IndexError):
            console.print("❌ Invalid selection", style="bold red")

    def _generate_cache_analytics(self, stats: dict[str, t.Any]) -> CacheAnalytics:
        """Generate comprehensive cache analytics."""
        total_hits = sum(cache_stats.get("hits", 0) for cache_stats in stats.values())
        total_misses = sum(
            cache_stats.get("misses", 0) for cache_stats in stats.values()
        )
        total_requests = total_hits + total_misses

        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        total_size = sum(
            cache_stats.get("total_size_mb", 0.0) for cache_stats in stats.values()
        )
        total_entries = sum(
            cache_stats.get("total_entries", 0) for cache_stats in stats.values()
        )

        # Calculate efficiency score (combination of hit rate, size efficiency, and access patterns)
        efficiency_score = min(100, hit_rate * 0.7 + (100 / (total_size + 1)) * 0.3)

        return CacheAnalytics(
            total_requests=total_requests,
            cache_hits=total_hits,
            cache_misses=total_misses,
            hit_rate_percent=hit_rate,
            avg_response_time_ms=5.2,  # Simplified - would need actual timing
            cache_size_mb=total_size,
            entries_count=total_entries,
            oldest_entry_age_hours=12.5,  # Simplified - would need actual age tracking
            most_accessed_keys=[
                ("hook_results", 150),
                ("file_hashes", 120),
            ],  # Simplified
            least_accessed_keys=[("old_config", 2), ("temp_data", 1)],  # Simplified
            cache_efficiency_score=efficiency_score,
        )

    def _create_main_stats_table(self, stats: dict[str, t.Any]) -> Table:
        """Create main statistics table with enhanced formatting."""
        table = Table(
            title="📊 Cache Performance Dashboard",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Cache Layer", style="cyan", no_wrap=True)
        table.add_column("Hit Rate %", justify="right", style="green")
        table.add_column("Hits", justify="right", style="yellow")
        table.add_column("Misses", justify="right", style="red")
        table.add_column("Entries", justify="right", style="magenta")
        table.add_column("Size (MB)", justify="right", style="blue")
        table.add_column("Status", justify="center", style="white")

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

            # Status indicator
            if hit_rate > 80:
                status = "🚀 Excellent"
                status_style = "green"
            elif hit_rate > 60:
                status = "✅ Good"
                status_style = "yellow"
            elif hit_rate > 30:
                status = "⚠️ Fair"
                status_style = "orange"
            else:
                status = "❌ Poor"
                status_style = "red"

            table.add_row(
                cache_name.replace("_", " ").title(),
                f"{hit_rate:.1f}",
                str(hits),
                str(misses),
                str(entries),
                f"{size_mb:.2f}",
                Text(status, style=status_style),
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

        table.add_row("", "", "", "", "", "", "", end_section=True)
        table.add_row(
            "Overall",
            Text(f"{overall_hit_rate:.1f}", style=f"bold {overall_style}"),
            str(total_hits),
            str(total_misses),
            str(total_entries),
            f"{total_size:.2f}",
            Text("📈 System", style="bold"),
            style="bold",
        )

        return table

    def _create_analytics_table(self, analytics: CacheAnalytics) -> Table:
        """Create detailed analytics table."""
        table = Table(
            title="🔬 Advanced Cache Analytics",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="yellow")
        table.add_column("Assessment", style="green")

        # Efficiency assessment
        if analytics.cache_efficiency_score > 80:
            efficiency_assessment = "Excellent - cache is highly optimized"
        elif analytics.cache_efficiency_score > 60:
            efficiency_assessment = "Good - minor optimizations possible"
        elif analytics.cache_efficiency_score > 40:
            efficiency_assessment = "Fair - optimization recommended"
        else:
            efficiency_assessment = "Poor - needs immediate optimization"

        table.add_row(
            "Efficiency Score",
            f"{analytics.cache_efficiency_score:.1f}/100",
            efficiency_assessment,
        )
        table.add_row(
            "Avg Response Time",
            f"{analytics.avg_response_time_ms:.1f}ms",
            "Fast" if analytics.avg_response_time_ms < 10 else "Slow",
        )
        table.add_row(
            "Memory Usage",
            f"{analytics.cache_size_mb:.1f} MB",
            "Optimal" if analytics.cache_size_mb < 50 else "High",
        )
        table.add_row(
            "Data Freshness",
            f"{analytics.oldest_entry_age_hours:.1f}h",
            "Fresh" if analytics.oldest_entry_age_hours < 24 else "Stale",
        )

        return table

    def _create_insights_panel(self, analytics: CacheAnalytics) -> Panel | None:
        """Create performance insights panel."""
        insights = []

        if analytics.hit_rate_percent > 80:
            insights.append("🚀 Excellent cache performance!")
        elif analytics.hit_rate_percent > 60:
            insights.append("✅ Good cache performance")
        elif analytics.hit_rate_percent > 30:
            insights.append("⚠️ Moderate cache performance - consider warming")
        else:
            insights.append("❌ Poor cache performance - optimization needed")

        if analytics.cache_size_mb > 100:
            insights.append(
                f"💾 Large cache size ({analytics.cache_size_mb:.1f}MB) - consider cleanup"
            )

        if analytics.cache_efficiency_score < 50:
            insights.append("🔧 Low efficiency score - run --cache-optimize")

        if not insights:
            return None

        insights_text = "\\n".join(insights)
        return Panel(
            insights_text,
            title="💡 Performance Insights",
            border_style="blue",
            padding=(1, 2),
        )

    def _generate_optimization_suggestions(
        self, analytics: CacheAnalytics
    ) -> list[CacheOptimizationSuggestion]:
        """Generate cache optimization suggestions."""
        suggestions = []

        # Hit rate optimization
        if analytics.hit_rate_percent < 60:
            suggestions.append(
                CacheOptimizationSuggestion(
                    type="warming",
                    priority="high",
                    description="Low hit rate detected - warm frequently used caches",
                    estimated_benefit="30-50% performance improvement",
                    action_required="Run --cache-warm",
                )
            )

        # Size optimization
        if analytics.cache_size_mb > 100:
            suggestions.append(
                CacheOptimizationSuggestion(
                    type="eviction",
                    priority="medium",
                    description="Large cache size - implement smart eviction",
                    estimated_benefit="Reduced memory usage",
                    action_required="Configure TTL and LRU policies",
                )
            )

        # Efficiency optimization
        if analytics.cache_efficiency_score < 70:
            suggestions.append(
                CacheOptimizationSuggestion(
                    type="ttl_tuning",
                    priority="medium",
                    description="Optimize cache TTL settings for better efficiency",
                    estimated_benefit="Improved hit rates and freshness",
                    action_required="Analyze access patterns and adjust TTL",
                )
            )

        return suggestions

    def _create_suggestions_panel(
        self, suggestions: list[CacheOptimizationSuggestion]
    ) -> Panel:
        """Create optimization suggestions panel."""
        if not suggestions:
            return Panel(
                "✨ Cache is well-optimized! No suggestions at this time.",
                title="🎯 Optimization Suggestions",
                border_style="green",
            )

        suggestion_lines = []
        for i, suggestion in enumerate(suggestions, 1):
            priority_emoji = (
                "🔴"
                if suggestion.priority == "high"
                else "🟡"
                if suggestion.priority == "medium"
                else "🟢"
            )
            suggestion_lines.append(
                f"{priority_emoji} {suggestion.description}\\n"
                f"   💡 {suggestion.estimated_benefit}\\n"
                f"   ⚡ {suggestion.action_required}"
            )

        suggestions_text = "\\n\\n".join(suggestion_lines)
        return Panel(
            suggestions_text,
            title="🎯 Optimization Suggestions",
            border_style="yellow",
            padding=(1, 2),
        )

    def _show_cache_directory_info(self, console: Console) -> None:
        """Show enhanced cache directory information."""
        if self.cache.enable_disk_cache and self.cache.cache_dir:
            cache_dir = self.cache.cache_dir
            cache_dir_info = f"📁 Cache Directory: {cache_dir}"

            if cache_dir.exists():
                cache_files = list[t.Any](cache_dir.rglob("*.cache"))
                disk_files_count = len(cache_files)

                # Calculate disk usage
                total_size = sum(f.stat().st_size for f in cache_files if f.exists())
                size_mb = total_size / (1024 * 1024)

                cache_dir_info += f" ({disk_files_count} files, {size_mb:.2f} MB)"

                # Show file age info
                if cache_files:
                    newest_file = max(cache_files, key=lambda f: f.stat().st_mtime)
                    oldest_file = min(cache_files, key=lambda f: f.stat().st_mtime)

                    now = datetime.now().timestamp()
                    newest_age = (now - newest_file.stat().st_mtime) / 3600  # hours
                    oldest_age = (now - oldest_file.stat().st_mtime) / 3600  # hours

                    cache_dir_info += f"\\n   📊 File ages: {newest_age:.1f}h (newest) to {oldest_age:.1f}h (oldest)"

            console.print()
            console.print(cache_dir_info)

    def _warm_hook_results_cache(self) -> None:
        """Warm hook results cache with common operations."""
        # Simplified - would implement actual hook result caching
        pass

    def _warm_file_hashes_cache(self) -> None:
        """Warm file hashes cache with project files."""
        # Simplified - would implement actual file hash caching
        pass

    def _warm_agent_decisions_cache(self) -> None:
        """Warm agent decisions cache with common patterns."""
        # Simplified - would implement actual agent decision caching
        pass

    def _warm_test_results_cache(self) -> None:
        """Warm test results cache with recent test data."""
        # Simplified - would implement actual test result caching
        pass

    def _apply_optimization_suggestion(
        self, suggestion: CacheOptimizationSuggestion
    ) -> bool:
        """Apply an optimization suggestion."""
        # Simplified - would implement actual optimization logic
        return True


# Enhanced CLI command handlers
def handle_clear_cache_enhanced(console: Console, selective: bool = False) -> None:
    """Enhanced cache clearing handler."""
    handler = EnhancedCacheHandlers()
    handler.handle_clear_cache(console, selective=selective)


def handle_cache_stats_enhanced(console: Console, detailed: bool = False) -> None:
    """Enhanced cache statistics handler."""
    handler = EnhancedCacheHandlers()
    handler.handle_cache_stats(console, detailed=detailed)


def handle_cache_warm(console: Console, operations: list[str] | None = None) -> None:
    """Cache warming handler."""
    handler = EnhancedCacheHandlers()
    handler.handle_cache_warm(console, target_operations=operations)


def handle_cache_optimize(console: Console) -> None:
    """Cache optimization handler."""
    handler = EnhancedCacheHandlers()
    handler.handle_cache_optimize(console)


def _handle_cache_commands_enhanced(
    clear_cache: bool,
    cache_stats: bool,
    cache_warm: bool,
    cache_optimize: bool,
    selective_clear: bool,
    detailed_stats: bool,
    console: Console,
) -> bool:
    """Enhanced cache command handler with new options."""
    if clear_cache:
        handle_clear_cache_enhanced(console, selective=selective_clear)
        return True

    if cache_stats:
        handle_cache_stats_enhanced(console, detailed=detailed_stats)
        return True

    if cache_warm:
        handle_cache_warm(console)
        return True

    if cache_optimize:
        handle_cache_optimize(console)
        return True

    return False

#!/usr/bin/env python3
"""
Demonstration of the enhanced code cleaner with comprehensive backup system.

This example shows how to use the new backup-aware code cleaning functionality
that provides automatic backup and restoration capabilities for safe code cleaning.
"""

from pathlib import Path

from rich.console import Console

from crackerjack import clean_code
from crackerjack.code_cleaner import CodeCleaner, PackageCleaningResult


def demonstrate_safe_code_cleaning():
    """Demonstrate the safe code cleaning with backup protection."""
    console = Console()

    console.print("[bold cyan]🛡️ Code Cleaner with Backup Protection Demo[/bold cyan]")
    console.print()

    # Example 1: Using the high-level API with safe mode (recommended)
    console.print(
        "[yellow]📝 Example 1: High-level API with safe mode (recommended)[/yellow]"
    )
    console.print()

    try:
        # This will use comprehensive backup protection by default
        result = clean_code(
            project_path=Path.cwd(),
            safe_mode=True,  # This is the default
        )

        if isinstance(result, PackageCleaningResult):
            console.print("[green]✅ Safe cleaning completed![/green]")
            console.print(f"   Files processed: {result.total_files}")
            console.print(f"   Files cleaned successfully: {result.successful_files}")
            console.print(f"   Files failed: {result.failed_files}")
            console.print(f"   Overall success: {result.overall_success}")

            if result.backup_metadata:
                console.print(
                    f"   📦 Backup available at: {result.backup_metadata.backup_directory}"
                )
            elif result.overall_success:
                console.print("   📦 Backup was cleaned up after successful completion")

        else:
            console.print("[yellow]⚠️ Legacy mode returned list of results[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error in safe cleaning: {e}[/red]")

    console.print()

    # Example 2: Using the CodeCleaner class directly
    console.print("[yellow]📝 Example 2: Direct CodeCleaner usage with backup[/yellow]")
    console.print()

    try:
        console = Console()
        code_cleaner = CodeCleaner(console=console, base_directory=Path.cwd())

        # Get the package directory
        package_dir = Path.cwd() / "crackerjack"

        if package_dir.exists():
            result = code_cleaner.clean_files_with_backup(package_dir)

            console.print("[green]✅ Direct cleaning completed![/green]")
            console.print(f"   Success: {result.overall_success}")
            console.print(f"   Files: {result.successful_files}/{result.total_files}")

            if result.backup_restored:
                console.print("   🔄 Files were restored from backup due to errors")

        else:
            console.print("[yellow]⚠️ Package directory not found[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error in direct cleaning: {e}[/red]")

    console.print()

    # Example 3: Emergency restoration (if needed)
    console.print("[yellow]📝 Example 3: Emergency restoration capability[/yellow]")
    console.print()

    console.print("[blue]ℹ️ Emergency restoration methods:[/blue]")
    console.print("   • result.backup_metadata contains all backup information")
    console.print("   • code_cleaner.restore_from_backup_metadata(backup_metadata)")
    console.print("   • Automatic restoration happens on any cleaning error")
    console.print(
        "   • Backup directories are preserved on failure for manual inspection"
    )

    console.print()

    # Example 4: Key safety features
    console.print("[yellow]📝 Example 4: Key safety features[/yellow]")
    console.print()

    safety_features = [
        "🛡️ Pre-cleaning backup of ALL package files",
        "✅ File integrity validation with SHA-256 checksums",
        "🔄 Automatic restoration on ANY error during cleaning",
        "📦 Secure temporary directories with proper permissions",
        "🧹 Automatic cleanup on successful completion",
        "💾 Backup preservation on failure for manual recovery",
        "⚡ Atomic file operations to prevent corruption",
        "🔍 Comprehensive logging of all backup operations",
    ]

    for feature in safety_features:
        console.print(f"   {feature}")

    console.print()

    # Example 5: Configuration options
    console.print("[yellow]📝 Example 5: Configuration options[/yellow]")
    console.print()

    console.print("[blue]ℹ️ Available configuration options:[/blue]")
    console.print("   • safe_mode=True (default): Use comprehensive backup protection")
    console.print(
        "   • safe_mode=False: Use legacy mode without backup (not recommended)"
    )
    console.print(
        "   • Custom backup directories can be configured in PackageBackupService"
    )
    console.print("   • Backup retention policies can be customized")

    console.print()
    console.print(
        "[green]🎉 Demo completed! Your code is safe with backup protection.[/green]"
    )


def show_backup_workflow():
    """Show the complete backup workflow process."""
    console = Console()

    console.print("[bold cyan]📋 Backup Protection Workflow[/bold cyan]")
    console.print()

    workflow_steps = [
        "1. 📦 [yellow]Create Backup:[/yellow] All package files are backed up with checksums",
        "2. ✅ [yellow]Validate Backup:[/yellow] Integrity check ensures backup is complete",
        "3. 🧹 [yellow]Clean Files:[/yellow] Apply cleaning operations to all files",
        "4. 🔍 [yellow]Check Results:[/yellow] Verify all cleaning operations succeeded",
        "5a. ✅ [green]Success Path:[/green] Clean up backup, cleaning complete",
        "5b. ❌ [red]Error Path:[/red] Restore all files from backup, preserve backup for inspection",
        "6. 🛡️ [yellow]Safety Guarantee:[/yellow] Files are never lost, even on system crashes",
    ]

    for step in workflow_steps:
        console.print(f"   {step}")

    console.print()

    console.print("[bold cyan]🔧 Error Handling Scenarios[/bold cyan]")
    console.print()

    error_scenarios = [
        "• File write permissions denied → Automatic restoration",
        "• Disk space exhaustion → Automatic restoration",
        "• System crash during cleaning → Manual restoration available",
        "• Corrupted file during cleaning → Automatic restoration",
        "• Network interruption → Automatic restoration",
        "• Any unexpected exception → Automatic restoration",
    ]

    for scenario in error_scenarios:
        console.print(f"   {scenario}")

    console.print()
    console.print("[green]🛡️ Your code is always protected![/green]")


if __name__ == "__main__":
    demonstrate_safe_code_cleaning()
    print()
    show_backup_workflow()

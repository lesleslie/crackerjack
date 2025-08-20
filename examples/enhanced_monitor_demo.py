# !/ usr / bin / env python3

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "crackerjack"))

from crackerjack.mcp.enhanced_progress_monitor import run_enhanced_monitor


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Enhanced Multi - Project Crackerjack Progress Monitor Demo"
    )
    parser.add_argument(
        " -- no - clear",
        action="store_true",
        help="Don't clear terminal before displaying",
    )
    parser.add_argument(
        " -- textual",
        action="store_true",
        help="Use Textual TUI instead of Rich display",
    )
    parser.add_argument(
        " -- refresh",
        type=float,
        default=0.5,
        help="Refresh interval in seconds (default: 0.5 for lively updates)",
    )

    args = parser.parse_args()

    print("🌟 Starting Enhanced Crackerjack Progress Monitor")
    print(" = " * 60)
    print("Features: ")
    print(" ✅ Multi - project autodiscovery")
    print(" ✅ Detailed error / failure counting")
    print(" ✅ Real - time metrics tracking with animated spinners")
    print(" ✅ Project path detection")
    print(" ✅ Terminal clearing & Textual support")
    print(" ⚡ Aggressive 0.5s refresh rate for lively updates")
    print(" 🎨 Animated progress bars and status indicators")
    print(" = " * 60)
    print()

    if args.textual:
        try:
            import textual.app  # noqa: F401

            print("🎨 Using Textual TUI interface...")
        except ImportError:
            print("⚠️ Textual not available, falling back to Rich display")
            args.textual = False

    print("🔍 Scanning for active Crackerjack MCP jobs...")
    print("💡 Tip: Start jobs in Claude Code with: / crackerjack: crackerjack")
    print(
        "📝 Note: Only MCP server jobs with job_ids are monitored, not regular CLI usage"
    )
    print()

    try:
        await run_enhanced_monitor(
            clear_terminal=not args.no_clear,
            use_textual=args.textual,
            refresh_interval=args.refresh,
        )
    except KeyboardInterrupt:
        print("\n🛑 Monitor stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

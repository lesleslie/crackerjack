import argparse
import asyncio

from crackerjack.mcp.enhanced_progress_monitor import run_enhanced_monitor


async def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Progress Monitor Demo (Fixed)"
    )
    parser.add_argument(
        " - - no - clear", action="store_true", help="Don't clear terminal"
    )
    parser.add_argument(
        " - - refresh", type=float, default=0.5, help="Refresh interval"
    )
    parser.add_argument(
        " - - no - watchdog", action="store_true", help="Disable watchdog services"
    )
    parser.add_argument(
        " - - no - textual", action="store_true", help="Use Rich instead of Textual"
    )

    args = parser.parse_args()

    print("🚀 Starting Enhanced Multi - Project Monitor (Fixed Version)")
    print("🐕 With dolphie - style improvements: ")
    print(" ✅ Timeout protection for connections")
    print(" ✅ Graceful error handling and fallback")
    print(" ✅ Better signal handling for clean shutdown")
    print(" ✅ Non - blocking startup")
    print()

    await run_enhanced_monitor(
        clear_terminal=not args.no_clear,
        use_textual=not args.no_textual,
        refresh_interval=args.refresh,
        enable_watchdog=not args.no_watchdog,
        websocket_url="ws: / / localhost: 8675",
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")

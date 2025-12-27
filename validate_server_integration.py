"""Phase 4 Server Integration Validation.

Tests that CrackerjackServer can successfully instantiate adapters.
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)


async def validate_server_integration():
    """Validate CrackerjackServer adapter instantiation."""
    print("=== Phase 4 Server Integration Validation ===\n")

    try:
        # Import server and settings
        from crackerjack.config import CrackerjackSettings, load_settings
        from crackerjack.server import CrackerjackServer

        print("✅ Imports successful")

        # Load settings
        settings = load_settings(CrackerjackSettings)
        print(f"✅ Settings loaded")

        # Create server instance
        server = CrackerjackServer(settings)
        print(f"✅ Server instance created")

        # Initialize adapters
        print("\nInitializing QA adapters...")
        await server._init_qa_adapters()

        # Check results
        print(f"\n✅ Adapter initialization complete")
        print(f"   Total adapters: {len(server.adapters)}")

        if server.adapters:
            print("\n   Initialized adapters:")
            for adapter in server.adapters:
                adapter_name = adapter.__class__.__name__
                print(f"     - {adapter_name}")
        else:
            print("   ⚠️  No adapters initialized (check settings flags)")

        # Test health snapshot
        print("\nTesting health snapshot...")
        health = server.get_health_snapshot()
        print(f"✅ Health snapshot generated")
        print(f"   Server status: {health['server_status']}")
        print(f"   QA adapters total: {health['qa_adapters']['total']}")
        print(f"   QA adapters healthy: {health['qa_adapters']['healthy']}")

        print("\n🎉 Server integration validation successful!")
        return True

    except Exception as e:
        print(f"\n❌ Server integration validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(validate_server_integration())
    sys.exit(0 if success else 1)

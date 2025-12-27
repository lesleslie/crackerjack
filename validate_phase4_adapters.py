"""Phase 4 Validation: Test all adapters work without ACB dependencies.

This script validates that all adapters updated in Phase 4 can:
1. Be imported without ACB dependencies
2. Be instantiated without errors
3. Have correct MODULE_ID and MODULE_STATUS constants
4. Use AdapterStatus enum instead of strings
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID


async def validate_adapters():
    """Validate all Phase 4 updated adapters."""
    print("=== Phase 4 Adapter Validation ===\n")

    errors = []
    successes = []

    # Test Type Adapters
    adapters_to_test = [
        ("crackerjack.adapters.type.pyrefly", "PyreflyAdapter", "25e1e5cf-d1f8-485e-85ab-01c8b540734a"),
        ("crackerjack.adapters.type.ty", "TyAdapter", "624df020-07cb-491f-9476-ca6daad3ba0b"),
        ("crackerjack.adapters.type.zuban", "ZubanAdapter", "e42fd557-ed29-4104-8edd-46607ab807e2"),
        ("crackerjack.adapters.refactor.skylos", "SkylosAdapter", "445401b8-b273-47f1-9015-22e721757d46"),
        ("crackerjack.adapters.refactor.refurb", "RefurbAdapter", "0f3546f6-4e29-4d9d-98f8-43c6f3c21a4e"),
        ("crackerjack.adapters.ai.claude", "ClaudeCodeFixer", "514c99ad-4f9a-4493-acca-542b0c43f95a"),
    ]

    for module_path, class_name, expected_uuid in adapters_to_test:
        print(f"Testing {module_path}.{class_name}...")

        try:
            # Import module
            module = __import__(module_path, fromlist=[class_name, "MODULE_ID", "MODULE_STATUS"])

            # Check MODULE_ID exists and matches expected
            if not hasattr(module, "MODULE_ID"):
                errors.append(f"  ❌ {module_path}: MODULE_ID not found")
                continue

            module_id = getattr(module, "MODULE_ID")
            if not isinstance(module_id, UUID):
                errors.append(f"  ❌ {module_path}: MODULE_ID is not a UUID")
                continue

            if str(module_id) != expected_uuid:
                errors.append(f"  ❌ {module_path}: MODULE_ID mismatch (expected {expected_uuid}, got {module_id})")
                continue

            # Check MODULE_STATUS exists and is AdapterStatus enum
            if not hasattr(module, "MODULE_STATUS"):
                errors.append(f"  ❌ {module_path}: MODULE_STATUS not found")
                continue

            module_status = getattr(module, "MODULE_STATUS")
            # Import AdapterStatus to check type
            from crackerjack.models.adapter_metadata import AdapterStatus

            if not isinstance(module_status, AdapterStatus):
                errors.append(f"  ❌ {module_path}: MODULE_STATUS is not AdapterStatus enum (got {type(module_status)})")
                continue

            # Check no ACB imports
            import inspect
            source = inspect.getsource(module)
            acb_imports = [
                "from acb.depends import depends",
                "from acb.cleanup import CleanupMixin",
                "from acb.config import Config",
                "from acb.adapters import",
                "from loguru import logger",
            ]

            found_acb = []
            for acb_import in acb_imports:
                if acb_import in source:
                    found_acb.append(acb_import)

            if found_acb:
                errors.append(f"  ❌ {module_path}: Found ACB imports: {found_acb}")
                continue

            # Try to instantiate (skip Claude which needs API key)
            if class_name != "ClaudeCodeFixer":
                adapter_class = getattr(module, class_name)
                adapter = adapter_class()

                # Try to init (should not fail even without settings for most adapters)
                try:
                    await adapter.init()
                except RuntimeError as e:
                    # Expected for some adapters that require settings
                    if "Settings not initialized" not in str(e):
                        errors.append(f"  ❌ {module_path}: Unexpected init error: {e}")
                        continue
            else:
                # Claude requires settings, just check it can be imported
                adapter_class = getattr(module, class_name)
                if not callable(adapter_class):
                    errors.append(f"  ❌ {module_path}: {class_name} is not callable")
                    continue

            successes.append(f"  ✅ {module_path}.{class_name}")
            print(f"  ✅ Passed all checks")

        except ImportError as e:
            errors.append(f"  ❌ {module_path}: Import failed - {e}")
        except Exception as e:
            errors.append(f"  ❌ {module_path}: Unexpected error - {e}")

        print()

    # Print summary
    print("\n=== Summary ===")
    print(f"Passed: {len(successes)}/{len(adapters_to_test)}")
    print(f"Failed: {len(errors)}/{len(adapters_to_test)}")

    if successes:
        print("\n✅ Successes:")
        for success in successes:
            print(success)

    if errors:
        print("\n❌ Errors:")
        for error in errors:
            print(error)
        return False

    print("\n🎉 All Phase 4 adapters validated successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(validate_adapters())
    sys.exit(0 if success else 1)

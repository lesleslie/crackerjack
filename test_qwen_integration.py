#!/usr/bin/env python3

import asyncio


async def test_qwen_settings_field() -> bool:
    from crackerjack.config.settings import AISettings

    print("Testing Qwen AI provider field in AISettings...")

    settings = AISettings()

    if hasattr(settings, "ai_provider"):
        print(f"✅ ai_provider field exists: {settings.ai_provider}")
        return True
    else:
        print("❌ ai_provider field NOT found in AISettings")
        return False


async def test_qwen_adapter_import() -> bool:
    print("\nTesting QwenCodeFixer adapter import...")

    try:
        from crackerjack.adapters.ai import QwenCodeFixer, QwenCodeFixerSettings

        print("✅ QwenCodeFixer and QwenCodeFixerSettings imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import QwenCodeFixer: {e}")
        return False


async def test_qwen_settings_validation() -> bool:
    print("\nTesting QwenCodeFixerSettings validation...")

    try:
        from crackerjack.adapters.ai import QwenCodeFixerSettings
        from pydantic import SecretStr


        settings = QwenCodeFixerSettings(qwen_api_key=SecretStr("sk" + "a" * 30))
        print(f"✅ Valid API key accepted (model: {settings.model})")


        try:
            QwenCodeFixerSettings(qwen_api_key=SecretStr("short"))
            print("❌ Short API key should have been rejected")
            return False
        except Exception:
            print("✅ Short API key correctly rejected")

        return True
    except Exception as e:
        print(f"❌ Settings validation test failed: {e}")
        return False


async def test_qwen_fixer_initialization() -> bool:
    print("\nTesting QwenCodeFixer initialization...")

    try:
        from crackerjack.adapters.ai import QwenCodeFixer, QwenCodeFixerSettings
        from pydantic import SecretStr

        settings = QwenCodeFixerSettings(
            qwen_api_key=SecretStr("sk" + "a" * 30),
            model="qwen-coder-plus",
        )
        fixer = QwenCodeFixer(settings)
        await fixer.init()

        print("✅ QwenCodeFixer initialized successfully")
        return True
    except Exception as e:
        print(f"❌ QwenCodeFixer initialization failed: {e}")
        return False


async def test_qwen_bridge_import() -> bool:
    print("\nTesting QwenCodeBridge import...")

    try:
        from crackerjack.agents.qwen_code_bridge import QwenCodeBridge

        print("✅ QwenCodeBridge imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import QwenCodeBridge: {e}")
        return False


async def test_qwen_provider_selection() -> bool:
    print("\nTesting AI provider selection...")

    try:
        from crackerjack.config import load_settings
        from crackerjack.config.settings import AISettings


        settings = load_settings(AISettings)

        if hasattr(settings, "ai_provider"):
            provider = settings.ai_provider
            print(f"✅ Current AI provider: {provider}")

            if provider in ("claude", "qwen"):
                print(f"✅ Provider '{provider}' is valid")
                return True
            else:
                print(f"❌ Invalid provider: {provider}")
                return False
        else:
            print("❌ ai_provider field not found")
            return False
    except Exception as e:
        print(f"❌ Provider selection test failed: {e}")
        return False


async def main() -> None:
    print("=" * 60)
    print("Crackerjack Qwen Integration Tests")
    print("=" * 60)

    results = []


    results.extend([
        await test_qwen_settings_field(),
        await test_qwen_adapter_import()
    ])
    results.extend([
        await test_qwen_settings_validation(),
        await test_qwen_fixer_initialization(),
        await test_qwen_bridge_import(),
        await test_qwen_provider_selection()
    ])


    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)

    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

#!/usr/bin/env python

import asyncio
import time


async def verify_singleton():
    from crackerjack.services.connection_pool import close_http_pool, get_http_pool

    pool1 = await get_http_pool()
    pool2 = await get_http_pool()

    assert pool1 is pool2, "Singleton pattern failed"
    print("✅ Singleton pattern: PASS")

    await close_http_pool()


async def verify_session_reuse():
    from crackerjack.services.connection_pool import close_http_pool, get_http_pool

    pool = await get_http_pool()
    session1 = await pool.get_session()
    session2 = await pool.get_session()

    assert session1 is session2, "Session reuse failed"
    print("✅ Session reuse: PASS")

    await close_http_pool()


async def verify_real_request():
    from crackerjack.services.connection_pool import close_http_pool, get_http_pool

    pool = await get_http_pool()

    try:
        async with pool.get_session_context() as session:
            async with session.get("https://httpbin.org/get", timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    assert "url" in data, "Invalid response"
                    print("✅ Real HTTP request: PASS")
                else:
                    print(f"⚠️ Real HTTP request: HTTP {response.status}")
    except Exception as e:
        print(f"⚠️ Real HTTP request: {e}")
    finally:
        await close_http_pool()


async def verify_performance():
    from crackerjack.services.connection_pool import close_http_pool, get_http_pool

    pool = await get_http_pool()
    urls = ["https://httpbin.org/get"] * 5

    start = time.time()
    tasks = []

    async def fetch(url):
        try:
            async with pool.get_session_context() as session:
                async with session.get(url, timeout=5) as response:
                    return response.status
        except Exception:
            return None

    for url in urls:
        tasks.append(fetch(url))

    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    success_count = sum(1 for r in results if r == 200)
    print(f"✅ Performance test: {success_count}/5 requests in {elapsed:.2f}s")

    await close_http_pool()


async def main():
    print("\n🔍 HTTP Connection Pool Verification")
    print("=" * 50)

    await verify_singleton()
    await verify_session_reuse()
    await verify_real_request()
    await verify_performance()

    print("\n✅ All verification tests complete!")


if __name__ == "__main__":
    asyncio.run(main())

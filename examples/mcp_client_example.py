# !/ usr / bin / env python3

import asyncio

import httpx


class CrackerjackMCPClient:

    def __init__(self, server_url: str = "http: // localhost: 8000") -> None:
        self.server_url = server_url
        self.client = httpx.AsyncClient()

    async def run_quality_workflow(self, project_path: str = ".") -> dict:
        results = {
            "project_path": project_path,
            "stages_completed": [],
            "fixes_applied": [],
            "final_status": "unknown",
        }

        try:

            print("🚀 Running fast hooks...")
            fast_result = await self.run_stage("fast")
            results["stages_completed"].append(fast_result)

            if not fast_result["success"]:
                print("⚠️ Fast hooks failed, applying auto - fixes...")
                fix_result = await self.apply_fixes("formatting")
                results["fixes_applied"].append(fix_result)


                fast_result = await self.run_stage("fast")
                results["stages_completed"].append(fast_result)

            if fast_result["success"]:
                print("✅ Fast hooks passed ! ")


                print("🧪 Running tests...")
                test_result = await self.run_stage("tests")
                results["stages_completed"].append(test_result)

                if test_result["success"]:
                    print("✅ Tests passed ! ")


                    print("🔍 Running comprehensive hooks...")
                    comp_result = await self.run_stage("comprehensive")
                    results["stages_completed"].append(comp_result)

                    if comp_result["success"]:
                        print("🎉 All quality checks passed ! ")
                        results["final_status"] = "success"
                    else:
                        print("⚠️ Comprehensive hooks need attention")
                        results["final_status"] = "partial_success"
                else:
                    print("❌ Tests failed")
                    results["final_status"] = "test_failure"
            else:
                print("❌ Fast hooks failed even after auto - fix")
                results["final_status"] = "fast_hooks_failure"

        except Exception as e:
            print(f"❌ Workflow error: {e}")
            results["final_status"] = "error"
            results["error"] = str(e)

        return results

    async def run_stage(self, stage: str, max_retries: int = 2) -> dict:
        payload = {
            "tool": "run_crackerjack_stage",
            "arguments": {"stage": stage, "max_retries": max_retries},
        }

        response = await self.client.post(f"{self.server_url} / execute", json = payload)
        return response.json()

    async def apply_fixes(self, fix_type: str, files: list[str] = None) -> dict:
        payload = {
            "tool": "apply_autofix",
            "arguments": {"fix_type": fix_type, "files": files},
        }

        response = await self.client.post(f"{self.server_url} / execute", json = payload)
        return response.json()

    async def analyze_errors(self, stage: str) -> dict:
        payload = {"tool": "analyze_errors", "arguments": {"stage": stage}}

        response = await self.client.post(f"{self.server_url} / execute", json = payload)
        return response.json()

    async def get_project_status(self) -> dict:
        payload = {"tool": "get_stage_status", "arguments": {}}

        response = await self.client.post(f"{self.server_url} / execute", json = payload)
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()


async def main() -> None:
    print("🤖 Crackerjack MCP Client Example")
    print(" = " * 50)

    client = CrackerjackMCPClient()

    try:

        print("📊 Getting project status...")
        status = await client.get_project_status()
        print(f"Project: {status.get('project_path', 'unknown')}")
        print(f"Auto - fix enabled: {status.get('autofix_enabled', False)}")


        print("\n🔄 Starting autonomous quality workflow...")
        results = await client.run_quality_workflow()


        print("\n📋 Workflow Results: ")
        print(f"Final Status: {results['final_status']}")
        print(f"Stages Completed: {len(results['stages_completed'])}")
        print(f"Fixes Applied: {len(results['fixes_applied'])}")

        if results["final_status"] == "success":
            print("\n🎉 Autonomous code quality enforcement completed successfully ! ")
        else:
            print(f"\n⚠️ Workflow completed with status: {results['final_status']}")

    except Exception as e:
        print(f"❌ Client error: {e}")
        print("Make sure the MCP server is running: ")
        print("python - m crackerjack -- start - mcp - server")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

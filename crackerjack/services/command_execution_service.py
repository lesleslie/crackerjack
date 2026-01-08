import asyncio
import subprocess
from pathlib import Path

from loguru import logger


class CommandExecutionService:
    def __init__(self, default_timeout: int = 30):
        self.default_timeout = default_timeout

    async def run_command(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        capture_output: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        timeout = timeout or self.default_timeout
        str_cmd = " ".join(cmd) if isinstance(cmd, list) else cmd
        logger.debug(f"Executing command: {str_cmd}")

        try:
            self._get_executable(cmd)
            process = await self._create_subprocess(cmd, capture_output, cwd, env)
            return await self._execute_process(
                process, cmd, str_cmd, timeout, check, capture_output
            )
        except FileNotFoundError:
            logger.error(f"Command not found: {self._get_executable(cmd)}")
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {str_cmd}, Error: {e}")
            raise

    def _get_executable(self, cmd: str | list[str]) -> str:
        if isinstance(cmd, list):
            return cmd[0] if cmd else ""
        else:
            parts = cmd.split()
            return parts[0] if parts else ""

    async def _create_subprocess(
        self,
        cmd: str | list[str],
        capture_output: bool,
        cwd: str | Path | None,
        env: dict[str, str] | None,
    ) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            *(cmd if isinstance(cmd, list) else cmd.split()),
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
            cwd=cwd,
            env=env,
        )

    async def _execute_process(
        self,
        process: asyncio.subprocess.Process,
        cmd: str | list[str],
        str_cmd: str,
        timeout: int,
        check: bool,
        capture_output: bool,
    ) -> subprocess.CompletedProcess:
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            return_code = process.returncode if process.returncode is not None else 0
            completed_process = subprocess.CompletedProcess(
                cmd,
                return_code,
                stdout.decode() if stdout else None,
                stderr.decode() if stderr else None,
            )

            if check and process.returncode != 0:
                logger.error(
                    f"Command failed with exit code {process.returncode}: {str_cmd}"
                )
                raise subprocess.CalledProcessError(
                    return_code,
                    cmd,
                    output=completed_process.stdout,
                    stderr=completed_process.stderr,
                )

            logger.debug(f"Command completed successfully: {str_cmd}")
            return completed_process

        except TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"Command timed out after {timeout}s: {str_cmd}")
            raise subprocess.TimeoutExpired(cmd, timeout)

    def run_command_sync(
        self,
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        capture_output: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        timeout = timeout or self.default_timeout
        str_cmd = " ".join(cmd) if isinstance(cmd, list) else cmd

        try:
            logger.debug(f"Executing sync command: {str_cmd}")

            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                timeout=timeout,
                capture_output=capture_output,
                text=True,
                check=check,
            )

            logger.debug(f"Sync command completed: {str_cmd}")
            return result

        except subprocess.TimeoutExpired:
            logger.error(f"Sync command timed out after {timeout}s: {str_cmd}")
            raise
        except Exception as e:
            logger.error(f"Sync command execution failed: {str_cmd}, Error: {e}")
            raise

    async def run_multiple_commands(
        self,
        commands: list[str | list[str]],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        parallel: bool = False,
    ) -> list[subprocess.CompletedProcess]:
        results = []

        if parallel:
            tasks = [
                self.run_command(cmd, cwd=cwd, env=env, timeout=timeout)
                for cmd in commands
            ]
            results = await asyncio.gather(*tasks)
        else:
            for cmd in commands:
                result = await self.run_command(cmd, cwd=cwd, env=env, timeout=timeout)
                results.append(result)

        return results

    async def command_exists(self, command: str) -> bool:
        try:
            import platform

            if platform.system() == "Windows":
                check_cmd = ["where", command]
            else:
                check_cmd = ["which", command]

            result = await self.run_command(
                check_cmd,
                capture_output=True,
                check=False,
            )

            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    async def run_command_with_retries(
        self,
        cmd: str | list[str],
        max_retries: int = 3,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        capture_output: bool = True,
        check: bool = True,
        backoff_factor: float = 1.0,
    ) -> subprocess.CompletedProcess:
        for attempt in range(max_retries + 1):
            try:
                return await self.run_command(
                    cmd,
                    cwd=cwd,
                    env=env,
                    timeout=timeout,
                    capture_output=capture_output,
                    check=check,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                if attempt == max_retries:
                    logger.error(f"Command failed after {max_retries} retries: {cmd}")
                    raise
                else:
                    wait_time = backoff_factor * (2**attempt)
                    logger.warning(
                        f"Command failed on attempt {attempt + 1}, "
                        f"retrying in {wait_time}s: {cmd}. Error: {e}"
                    )
                    await asyncio.sleep(wait_time)

        raise RuntimeError("Unexpected error in run_command_with_retries")

"""Unified command execution service with consistent error handling and timeouts."""

import asyncio
import subprocess
from pathlib import Path

from loguru import logger


class CommandExecutionService:
    """Unified command execution with consistent error handling, timeouts, and caching."""

    def __init__(self, default_timeout: int = 30):
        """
        Initialize the command execution service.

        Args:
            default_timeout: Default timeout in seconds for commands
        """
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
        """
        Run a command with timeout and error handling.

        Args:
            cmd: Command to run as a string or list of strings
            cwd: Working directory to run the command in
            env: Environment variables to use
            timeout: Timeout in seconds (uses default if not specified)
            capture_output: Whether to capture stdout/stderr
            check: If True, raises exception on non-zero exit code

        Returns:
            CompletedProcess instance with results

        Raises:
            subprocess.TimeoutExpired: If command times out
            subprocess.CalledProcessError: If command fails and check=True
        """
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
        """Extract executable name from command."""
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
        """Create subprocess with proper configuration."""
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
        """Execute the process and handle the result."""
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
            # Handle timeout
            process.kill()
            await process.wait()  # Ensure process is cleaned up
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
        """
        Synchronous version of run_command.

        Args:
            cmd: Command to run as a string or list of strings
            cwd: Working directory to run the command in
            env: Environment variables to use
            timeout: Timeout in seconds (uses default if not specified)
            capture_output: Whether to capture stdout/stderr
            check: If True, raises exception on non-zero exit code

        Returns:
            CompletedProcess instance with results
        """
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
                text=True,  # Return strings instead of bytes
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
        """
        Run multiple commands sequentially or in parallel.

        Args:
            commands: List of commands to run
            cwd: Working directory to run the commands in
            env: Environment variables to use
            timeout: Timeout in seconds for each command
            parallel: If True, run commands in parallel; otherwise sequentially

        Returns:
            List of CompletedProcess instances with results
        """
        results = []

        if parallel:
            # Run commands in parallel
            tasks = [
                self.run_command(cmd, cwd=cwd, env=env, timeout=timeout)
                for cmd in commands
            ]
            results = await asyncio.gather(*tasks)
        else:
            # Run commands sequentially
            for cmd in commands:
                result = await self.run_command(cmd, cwd=cwd, env=env, timeout=timeout)
                results.append(result)

        return results

    async def command_exists(self, command: str) -> bool:
        """
        Check if a command exists in the system.

        Args:
            command: Command to check

        Returns:
            True if command exists, False otherwise
        """
        try:
            # Try running 'which' on Unix-like systems or 'where' on Windows
            import platform

            if platform.system() == "Windows":
                check_cmd = ["where", command]
            else:
                check_cmd = ["which", command]

            result = await self.run_command(
                check_cmd,
                capture_output=True,
                check=False,  # Don't raise on non-zero exit (which returns 1 if not found)
            )

            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If the check command itself fails, command likely doesn't exist
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
        """
        Run a command with retry logic.

        Args:
            cmd: Command to run
            max_retries: Maximum number of retry attempts
            cwd: Working directory
            env: Environment variables
            timeout: Timeout for each attempt
            capture_output: Whether to capture output
            check: Whether to check return code
            backoff_factor: Factor by which to multiply wait time between retries

        Returns:
            CompletedProcess instance with results
        """
        for attempt in range(
            max_retries + 1
        ):  # +1 because first attempt doesn't count as retry
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
                    # Last attempt, re-raise the exception
                    logger.error(f"Command failed after {max_retries} retries: {cmd}")
                    raise
                else:
                    # Wait before retrying with exponential backoff
                    wait_time = backoff_factor * (2**attempt)
                    logger.warning(
                        f"Command failed on attempt {attempt + 1}, "
                        f"retrying in {wait_time}s: {cmd}. Error: {e}"
                    )
                    await asyncio.sleep(wait_time)

        # This line should never be reached due to the loop logic
        raise RuntimeError("Unexpected error in run_command_with_retries")

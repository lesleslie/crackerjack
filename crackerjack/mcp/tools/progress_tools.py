import contextlib
import json
import typing as t
from pathlib import Path

from crackerjack.mcp.context import get_context


def _create_progress_file(job_id: str) -> Path:
    import re
    import tempfile

    if not job_id or not isinstance(job_id, str):
        msg = f"Invalid job_id: {job_id}"
        raise ValueError(msg)
    if not re.match(r"^[a-zA-Z0-9_-]+$", job_id):
        msg = f"Invalid job_id format: {job_id}"
        raise ValueError(msg)

    context = get_context()
    if context:
        return context.progress_dir / f"job-{job_id}.json"
    progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
    progress_dir.mkdir(exist_ok=True)
    return progress_dir / f"job-{job_id}.json"


def _update_progress(
    job_id: str,
    status: str = "running",
    iteration: int = 1,
    max_iterations: int = 10,
    overall_progress: int = 0,
    current_stage: str = "initialization",
    stage_progress: int = 0,
    message: str = "",
) -> None:
    try:
        progress_file = _create_progress_file(job_id)

        progress_data = {
            "job_id": job_id,
            "status": status,
            "iteration": iteration,
            "max_iterations": max_iterations,
            "overall_progress": min(100, max(0, overall_progress)),
            "current_stage": current_stage,
            "stage_progress": min(100, max(0, stage_progress)),
            "message": message,
            "timestamp": get_context().get_current_time() if get_context() else "",
        }

        progress_file.write_text(json.dumps(progress_data, indent=2))

        context = get_context()
        if context and hasattr(context, "websocket_progress_queue"):
            with contextlib.suppress(Exception):
                context.websocket_progress_queue.put_nowait(progress_data)

    except Exception as e:
        context = get_context()
        if context:
            context.safe_print(f"Warning: Failed to update progress for {job_id}: {e}")


def _handle_get_job_progress(job_id: str) -> str:
    context = get_context()
    if not context:
        return '{"error": "Server context not available"}'

    if not context.validate_job_id(job_id):
        return f'{{"error": "Invalid job_id: {job_id}"}}'

    try:
        progress_file = _create_progress_file(job_id)

        if not progress_file.exists():
            return f'{{"error": "Job {job_id} not found", "job_id": "{job_id}"}}'

        progress_data = json.loads(progress_file.read_text())
        return json.dumps(progress_data, indent=2)

    except json.JSONDecodeError as e:
        return f'{{"error": "Invalid progress data for job {job_id}: {e}"}}'
    except Exception as e:
        return f'{{"error": "Failed to get progress for job {job_id}: {e}"}}'


def _execute_session_action(
    state_manager,
    action: str,
    checkpoint_name: str | None,
    context,
) -> str:
    if action == "start":
        state_manager.start_session()
        return '{"status": "session_started", "action": "start"}'

    if action == "checkpoint":
        checkpoint_name = checkpoint_name or f"checkpoint_{context.get_current_time()}"
        state_manager.create_checkpoint(checkpoint_name)
        return f'{{"status": "checkpoint_created", "action": "checkpoint", "name": "{checkpoint_name}"}}'

    if action == "complete":
        state_manager.complete_session()
        return '{"status": "session_completed", "action": "complete"}'

    if action == "reset":
        state_manager.reset_session()
        return '{"status": "session_reset", "action": "reset"}'

    return f'{{"error": "Invalid action: {action}. Valid actions: start, checkpoint, complete, reset"}}'


def _handle_session_management(action: str, checkpoint_name: str | None = None) -> str:
    context = get_context()
    if not context:
        return '{"error": "Server context not available"}'

    try:
        state_manager = getattr(context, "state_manager", None)
        if not state_manager:
            return '{"error": "State manager not available"}'

        return _execute_session_action(state_manager, action, checkpoint_name, context)

    except Exception as e:
        return f'{{"error": "Session management failed: {e}"}}'


def register_progress_tools(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_job_progress(job_id: str) -> str:
        return _handle_get_job_progress(job_id)

    @mcp_app.tool()
    async def session_management(
        action: str,
        checkpoint_name: str | None = None,
    ) -> str:
        return _handle_session_management(action, checkpoint_name)

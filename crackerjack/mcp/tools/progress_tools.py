import contextlib
import json
import typing as t
from pathlib import Path

from crackerjack.mcp.context import get_context
from crackerjack.services.input_validator import get_input_validator


def _create_progress_file(job_id: str) -> Path:
    import tempfile

    job_id_result = get_input_validator().validate_job_id(job_id)

    if not job_id_result.valid:
        msg = f"Invalid job_id: {job_id_result.error_message}"
        raise ValueError(msg)

    sanitized_job_id = job_id_result.sanitized_value

    context = get_context()
    if context:
        return context.progress_dir / f"job-{sanitized_job_id}.json"

    progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
    progress_dir.mkdir(exist_ok=True, mode=0o750)
    return progress_dir / f"job-{sanitized_job_id}.json"


def _clamp_progress(value: int) -> int:
    return min(100, max(0, value))


def _get_timestamp() -> str:
    context = get_context()
    return context.get_current_time() if context else ""


def _build_dict_format_progress(
    job_id: str,
    progress_data: dict[str, t.Any],
    iteration: int,
    max_iterations: int,
    overall_progress: int,
    current_stage: str,
    stage_progress: int,
    message: str,
) -> dict[str, t.Any]:
    return {
        "job_id": job_id,
        "status": progress_data.get("status", "running"),
        "iteration": progress_data.get("iteration", iteration),
        "max_iterations": progress_data.get("max_iterations", max_iterations),
        "overall_progress": _clamp_progress(
            progress_data.get("overall_progress", overall_progress)
        ),
        "current_stage": progress_data.get("type", current_stage),
        "stage_progress": _clamp_progress(
            progress_data.get("stage_progress", stage_progress)
        ),
        "message": progress_data.get("message", message),
        "timestamp": _get_timestamp(),
    }


def _build_legacy_format_progress(
    job_id: str,
    progress_data: str | None,
    iteration: int,
    max_iterations: int,
    overall_progress: int,
    current_stage: str,
    stage_progress: int,
    message: str,
) -> dict[str, t.Any]:
    status = progress_data if isinstance(progress_data, str) else "running"
    return {
        "job_id": job_id,
        "status": status,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "overall_progress": _clamp_progress(overall_progress),
        "current_stage": current_stage,
        "stage_progress": _clamp_progress(stage_progress),
        "message": message,
        "timestamp": _get_timestamp(),
    }


def _notify_websocket(final_progress_data: dict[str, t.Any]) -> None:
    context = get_context()
    if context and hasattr(context, "websocket_progress_queue"):
        with contextlib.suppress(Exception):
            context.websocket_progress_queue.put_nowait(final_progress_data)


def _update_progress(
    job_id: str,
    progress_data: dict[str, t.Any] | str | None = None,
    context: t.Any = None,
    iteration: int = 1,
    max_iterations: int = 5,
    overall_progress: int = 0,
    current_stage: str = "initialization",
    stage_progress: int = 0,
    message: str = "",
) -> None:
    try:
        progress_file = _create_progress_file(job_id)

        if isinstance(progress_data, dict):
            final_progress_data = _build_dict_format_progress(
                job_id,
                progress_data,
                iteration,
                max_iterations,
                overall_progress,
                current_stage,
                stage_progress,
                message,
            )
        else:
            final_progress_data = _build_legacy_format_progress(
                job_id,
                progress_data,
                iteration,
                max_iterations,
                overall_progress,
                current_stage,
                stage_progress,
                message,
            )

        progress_file.write_text(json.dumps(final_progress_data, indent=2))
        _notify_websocket(final_progress_data)

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


async def _execute_session_action(
    state_manager: t.Any,
    action: str,
    checkpoint_name: str | None,
    context: t.Any,
) -> str:
    if action == "start":
        state_manager.start_session()
        return '{"status": "session_started", "action": "start"}'

    if action == "checkpoint":
        checkpoint_name = checkpoint_name or f"checkpoint_{context.get_current_time()}"
        await state_manager.save_checkpoint(checkpoint_name)
        return f'{{"status": "checkpoint_created", "action": "checkpoint", "name": "{checkpoint_name}"}}'

    if action == "complete":
        state_manager.complete_session()
        return '{"status": "session_completed", "action": "complete"}'

    if action == "reset":
        state_manager.reset_session()
        return '{"status": "session_reset", "action": "reset"}'

    return f'{{"error": "Invalid action: {action}. Valid actions: start, checkpoint, complete, reset"}}'


async def _handle_session_management(
    action: str, checkpoint_name: str | None = None
) -> str:
    context = get_context()
    if not context:
        return '{"error": "Server context not available"}'

    try:
        state_manager = getattr(context, "state_manager", None)
        if not state_manager:
            return '{"error": "State manager not available"}'

        return await _execute_session_action(
            state_manager, action, checkpoint_name, context
        )

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
        return await _handle_session_management(action, checkpoint_name)

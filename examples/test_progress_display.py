# !/ usr / bin / env python3

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crackerjack.mcp.progress_monitor import display_progress_update

progress_states = [
    {
        "job_id": "test - job - 123",
        "status": "running",
        "iteration": 1,
        "max_iterations": 10,
        "overall_progress": 10,
        "current_stage": "fast_hooks",
        "stage_progress": 2,
        "stage_total": 5,
        "stage_percentage": 40,
        "message": "Running fast hooks...",
    },
    {
        "job_id": "test - job - 123",
        "status": "running",
        "iteration": 1,
        "max_iterations": 10,
        "overall_progress": 25,
        "current_stage": "comprehensive_hooks",
        "stage_progress": 3,
        "stage_total": 6,
        "stage_percentage": 50,
        "message": "Running comprehensive hooks...",
    },
    {
        "job_id": "test - job - 123",
        "status": "running",
        "iteration": 1,
        "max_iterations": 10,
        "overall_progress": 40,
        "current_stage": "tests",
        "stage_progress": 150,
        "stage_total": 300,
        "stage_percentage": 50,
        "message": "Running tests...",
    },
    {
        "job_id": "test - job - 123",
        "status": "running",
        "iteration": 2,
        "max_iterations": 10,
        "overall_progress": 55,
        "current_stage": "analyzing",
        "message": "Analyzing errors and planning fixes...",
    },
    {
        "job_id": "test - job - 123",
        "status": "running",
        "iteration": 2,
        "max_iterations": 10,
        "overall_progress": 70,
        "current_stage": "fixing",
        "message": "Applying auto - fixes to source code...",
    },
    {
        "job_id": "test - job - 123",
        "status": "completed",
        "iteration": 2,
        "max_iterations": 10,
        "overall_progress": 100,
        "details": {
            "errors_fixed": 15,
            "tests_passed": 300,
            "final_message": "All code quality checks passed after 2 iterations",
        },
    },
]

print("Demonstrating Crackerjack Progress Display: \n")

for state in progress_states:
    display_progress_update(state)
    print()
    time.sleep(1)

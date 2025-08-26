# Paranoid Verification Workflow

## Core Principle: Assume Failure Until Proven Otherwise

Every action in our workflow must be verified. Success is never assumed - it must be proven through multiple verification methods.

## Verification Protocol

### 1. Pre-Action State Capture

```python
def capture_pre_action_state():
    """Capture complete system state before any action."""
    state = {
        "timestamp": time.time(),
        "location": {
            "desktop": get_current_desktop(),
            "app": get_frontmost_app(),
            "window": get_window_info(),
            "tab": get_tab_info(),
        },
        "processes": {
            "mcp_server": check_process("crackerjack.*mcp"),
            "websocket": check_process("websocket.*8675"),
            "monitor": check_process("enhanced_progress_monitor"),
        },
        "network": {
            "websocket_port": check_port(8675),
            "websocket_responsive": test_websocket_connection(),
        },
        "files": {
            "progress_dir": list_progress_files(),
            "active_jobs": get_active_job_ids(),
        },
        "screenshot": take_screenshot("pre_action"),
    }
    return state
```

### 2. Action Execution with Logging

```python
def execute_action_with_verification(action_func, *args, **kwargs):
    """Execute action with comprehensive logging and verification."""

    # Step 1: Pre-action state
    pre_state = capture_pre_action_state()
    log_state("PRE-ACTION", pre_state)

    # Step 2: Execute action
    start_time = time.time()
    try:
        result = action_func(*args, **kwargs)
        execution_time = time.time() - start_time
        success = True
        error = None
    except Exception as e:
        result = None
        execution_time = time.time() - start_time
        success = False
        error = str(e)

    # Step 3: Post-action state
    time.sleep(0.5)  # Brief delay for state to settle
    post_state = capture_post_action_state()
    log_state("POST-ACTION", post_state)

    # Step 4: Verify success
    verification = verify_action_success(pre_state, post_state, result)

    return {
        "success": success and verification["verified"],
        "result": result,
        "error": error,
        "execution_time": execution_time,
        "pre_state": pre_state,
        "post_state": post_state,
        "verification": verification,
    }
```

### 3. Multi-Point Verification

```python
def verify_action_success(pre_state, post_state, expected_result):
    """Verify action success through multiple checks."""
    checks = {
        "location_correct": False,
        "process_healthy": False,
        "network_accessible": False,
        "expected_changes": False,
        "no_errors": False,
    }

    # Location verification
    if action_type == "window_switch":
        checks["location_correct"] = (
            post_state["location"]["window"] == expected_window
            and post_state["location"]["tab"] == expected_tab
        )

    # Process verification
    checks["process_healthy"] = all(
        post_state["processes"][proc] for proc in required_processes
    )

    # Network verification
    if requires_network:
        checks["network_accessible"] = (
            post_state["network"]["websocket_responsive"]
            and post_state["network"]["websocket_port"]
        )

    # Expected changes verification
    checks["expected_changes"] = verify_expected_changes(pre_state, post_state)

    # Error detection
    checks["no_errors"] = not detect_error_conditions(post_state)

    # Overall verification
    verified = all(checks.values())

    return {
        "verified": verified,
        "checks": checks,
        "details": generate_verification_report(checks, pre_state, post_state),
    }
```

## Workflow Implementation

### Window Switching with Verification

```python
class VerifiedWorkflow:
    def switch_to_monitor_window(self):
        """Switch to Window 2, Tab 2 with full verification."""

        # 1. Capture current state
        print("📸 Capturing pre-switch state...")
        pre_state = self.capture_state()

        # 2. Take pre-action screenshot
        pre_screenshot = self.take_screenshot("pre_switch")

        # 3. Log current location
        print(f"📍 Current location: {pre_state['location']}")

        # 4. Execute switch
        print("🔄 Attempting to switch to Window 2, Tab 2...")
        switch_result = self.execute_window_switch(2, 2)

        # 5. Wait for switch to complete
        time.sleep(1)

        # 6. Capture post-switch state
        print("📸 Capturing post-switch state...")
        post_state = self.capture_state()

        # 7. Take post-action screenshot
        post_screenshot = self.take_screenshot("post_switch")

        # 8. Verify switch success
        verification = self.verify_switch(pre_state, post_state, 2, 2)

        if not verification["success"]:
            print("❌ Switch verification failed!")
            print(f"   Expected: Window 2, Tab 2")
            print(f"   Actual: {post_state['location']}")

            # Attempt recovery
            return self.recover_from_failed_switch(pre_state, post_state)

        print("✅ Switch verified successfully!")
        return True
```

### Command Execution with Verification

```python
def execute_monitor_command(self):
    """Execute monitor command with full verification."""

    # 1. Verify we're in correct location
    if not self.verify_current_location(2, 2):
        print("❌ Not in correct location for monitor execution")
        return False

    # 2. Check pre-conditions
    pre_checks = {
        "websocket_running": self.check_websocket_server(),
        "port_available": not self.check_port_in_use(8675),
        "no_existing_monitor": not self.check_process("enhanced_progress_monitor"),
    }

    if not all(pre_checks.values()):
        print("❌ Pre-conditions not met:")
        for check, result in pre_checks.items():
            print(f"   {check}: {result}")
        return False

    # 3. Execute command
    print("💻 Executing monitor command...")
    command = "python -m crackerjack --monitor"

    # Take screenshot before command
    self.take_screenshot("pre_command")

    # Execute
    result = self.send_command_to_terminal(command)

    # 4. Wait and verify startup
    print("⏳ Waiting for monitor startup...")
    for i in range(10):  # 10 second timeout
        time.sleep(1)

        # Check if monitor process started
        if self.check_process("enhanced_progress_monitor"):
            print(f"✅ Monitor process detected after {i + 1} seconds")
            break

        # Check for error output
        if self.detect_terminal_error():
            print("❌ Error detected in terminal output")
            self.take_screenshot("error_detected")
            return False
    else:
        print("❌ Monitor failed to start within timeout")
        return False

    # 5. Verify monitor is functional
    monitor_checks = {
        "process_running": self.check_process("enhanced_progress_monitor"),
        "ui_visible": self.verify_textual_ui_active(),
        "websocket_connected": self.verify_websocket_connection(),
        "panels_rendered": self.verify_monitor_panels(),
    }

    print("🔍 Verifying monitor functionality...")
    for check, result in monitor_checks.items():
        print(f"   {check}: {'✅' if result else '❌'}")

    return all(monitor_checks.values())
```

### Socket Communication Verification

```python
async def verify_websocket_connection(self):
    """Verify WebSocket server is responsive."""
    try:
        async with websockets.connect("ws://localhost:8675") as ws:
            # Send ping
            await ws.send(json.dumps({"type": "ping"}))

            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)

            return data.get("type") == "pong"
    except Exception as e:
        print(f"❌ WebSocket verification failed: {e}")
        return False
```

### Process Verification

```python
def check_process(self, pattern):
    """Check if process matching pattern is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_process_info(self, pattern):
    """Get detailed process information."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)

        processes = []
        for line in result.stdout.split("\n"):
            if pattern in line and "grep" not in line:
                parts = line.split()
                processes.append(
                    {
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": " ".join(parts[10:]),
                    }
                )

        return processes
    except Exception as e:
        print(f"❌ Process info error: {e}")
        return []
```

## Verification Checklist

### For Every Action:

- [ ] **Pre-Action**

  - [ ] Capture current desktop/app/window/tab location
  - [ ] Take screenshot with timestamp
  - [ ] Check relevant process states
  - [ ] Verify network/socket availability
  - [ ] Log complete state to file

- [ ] **During Action**

  - [ ] Log action start time
  - [ ] Capture any output/errors
  - [ ] Monitor for unexpected behavior
  - [ ] Set reasonable timeout

- [ ] **Post-Action**

  - [ ] Wait brief moment for state to settle
  - [ ] Capture new desktop/app/window/tab location
  - [ ] Take screenshot with timestamp
  - [ ] Re-check process states
  - [ ] Verify expected changes occurred
  - [ ] Verify no unexpected changes occurred

- [ ] **Verification**

  - [ ] Compare pre/post states
  - [ ] Verify all expected changes
  - [ ] Check for error conditions
  - [ ] Generate verification report
  - [ ] Make success/failure determination

- [ ] **Recovery**

  - [ ] If verification fails, attempt recovery
  - [ ] Log failure details
  - [ ] Take diagnostic screenshots
  - [ ] Return to known good state
  - [ ] Report failure clearly

## Example: Complete Monitor Startup Workflow

```python
def start_monitor_with_paranoid_verification(self):
    """Start monitor with complete verification at every step."""

    workflow_id = f"monitor_start_{int(time.time())}"
    log_file = f"/tmp/workflow_{workflow_id}.log"

    # Initialize workflow log
    self.init_workflow_log(workflow_id, log_file)

    try:
        # Step 1: Verify initial conditions
        if not self.verify_initial_conditions():
            raise WorkflowError("Initial conditions not met")

        # Step 2: Save current location
        original_location = self.save_current_location()

        # Step 3: Switch to monitor window
        if not self.switch_to_monitor_window_verified():
            raise WorkflowError("Failed to switch to monitor window")

        # Step 4: Start monitor
        if not self.start_monitor_verified():
            raise WorkflowError("Failed to start monitor")

        # Step 5: Verify monitor running
        if not self.verify_monitor_operational():
            raise WorkflowError("Monitor not operational")

        # Step 6: Return to original location
        if not self.return_to_location_verified(original_location):
            print("⚠️  Could not return to original location")

        print(f"✅ Workflow completed successfully!")
        print(f"📄 Log file: {log_file}")
        return True

    except WorkflowError as e:
        print(f"❌ Workflow failed: {e}")
        self.capture_failure_diagnostics(workflow_id)
        return False
```

## Key Principles

1. **Never Trust, Always Verify**: Every action must be verified
1. **Multiple Verification Points**: Use screenshots, process checks, socket tests, and state comparison
1. **Detailed Logging**: Every step creates evidence of what happened
1. **Graceful Failure**: When verification fails, gather diagnostics and attempt recovery
1. **Clear Reporting**: Success and failure must be unambiguous

This paranoid verification approach ensures reliability and provides clear diagnostics when things go wrong.

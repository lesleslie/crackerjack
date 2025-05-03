# Testing with Crackerjack

This document provides information about running tests with Crackerjack.

## Optimized Test Setup

Crackerjack uses an optimized test setup for all packages to prevent hanging issues. This setup:

1. Avoids aggressive process killing that could cause issues with test reporting and cleanup
2. Uses a more targeted approach to cleaning up asyncio tasks
3. Reduces excessive mocking that could cause stability issues
4. Sets appropriate environment variables to control asyncio behavior

## Running Tests

To run tests with the optimized setup, use:

```bash
crackerjack --test
```

This command applies the same optimized settings to all packages, ensuring consistent behavior and preventing hanging issues.

## Test Architecture

Crackerjack uses a modular approach to test execution, broken down into several specialized components:

1. **Test Command Preparation** - Builds the pytest command with appropriate options
2. **Environment Setup** - Configures environment variables for optimal test execution
3. **Process Execution** - Manages the subprocess with timeout handling and output streaming
4. **Results Reporting** - Processes and displays test results with appropriate formatting

This modular design improves maintainability and makes the testing process more robust.

### Implementation Details

The test execution is implemented through several specialized methods:

- `_prepare_pytest_command`: Constructs the pytest command with all necessary options based on user preferences
- `_setup_test_environment`: Sets environment variables to optimize test execution and prevent hanging
- `_run_pytest_process`: Manages the subprocess execution with real-time output streaming and timeout handling
- `_report_test_results`: Processes test results and provides appropriate feedback to the user
- `_run_tests`: Orchestrates the entire testing process by calling the specialized methods in sequence

This separation of concerns makes the code more maintainable and easier to test.

## Test Configuration

The test configuration is standardized across all packages and includes the following optimizations:

### Pytest Options

- `--no-cov`: Disables coverage reporting which can cause hanging
- `--capture=fd`: Captures stdout/stderr at file descriptor level for better output handling
- `--tb=short`: Uses shorter traceback format to reduce output complexity
- `--no-header`: Reduces output noise
- `--disable-warnings`: Disables warning capture which can cause issues
- `--durations=0`: Shows slowest tests to help identify potential hanging tests
- `--timeout=300`: Sets a 5-minute timeout for tests

### Process Management

Crackerjack uses a custom process management approach that:

1. Runs pytest with a timeout to ensure tests don't run indefinitely
2. Streams output in real-time to provide feedback during test execution
3. Properly handles process termination and cleanup
4. Ensures proper process cleanup even if tests hang

### Environment Variables

Crackerjack sets several environment variables to control test behavior:

- `RUNNING_UNDER_CRACKERJACK=1` - Signals to test frameworks that tests are being run by crackerjack
- `PYTHONASYNCIO_DEBUG=0` - Disables asyncio debug mode
- `PYTEST_ASYNCIO_MODE=strict` - Uses a stricter asyncio mode that helps prevent hanging

## Troubleshooting

If you encounter issues with tests:

1. Make sure you're using the latest version of crackerjack
2. Try running with the `--verbose` flag to see more detailed output
3. Check the test logs for any specific errors or warnings
4. Look for timeout messages that might indicate which tests are hanging

### Common Issues

#### Hanging Tests

If tests are hanging, the built-in timeout (5 minutes) will eventually terminate the process. The output will include a message indicating that the test execution timed out. To debug:

1. Run with `--verbose` to see more detailed output
2. Check for tests that might be creating infinite loops or waiting indefinitely for resources
3. Look for asyncio-related issues, which are a common cause of hanging tests

#### Environment Variable Conflicts

If you have environment variables set in your shell that conflict with those set by Crackerjack, you might experience unexpected behavior. To troubleshoot:

1. Check your environment for variables like `PYTEST_ASYNCIO_MODE` or `PYTHONASYNCIO_DEBUG`
2. Consider running in a clean environment if necessary

#### Process Management Issues

If you encounter issues with process management (e.g., zombie processes or resource leaks):

1. Make sure you're using the latest version of Crackerjack
2. Check for any system-specific issues that might affect process management
3. Consider running with fewer concurrent tests if your system has limited resources

## Extending Test Functionality

The modular design of Crackerjack's test execution makes it easy to extend or customize the testing process:

### Adding New Test Options

To add new pytest options, modify the `_prepare_pytest_command` method to include additional options in the command list.

### Customizing Environment Setup

To change environment variable settings, modify the `_setup_test_environment` method to set additional variables or change existing ones.

### Enhancing Process Management

To improve process management or output handling, modify the `_run_pytest_process` method to implement custom behavior.

### Customizing Result Reporting

To change how test results are reported, modify the `_report_test_results` method to implement custom formatting or additional actions based on test outcomes.

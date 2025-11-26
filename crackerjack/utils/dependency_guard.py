"""
Dependency Guard module to ensure proper dependency injection.

This module provides utilities to ensure that dependencies are properly
registered in the ACB dependency injection system and to handle cases
where dependencies might be registered as empty tuples or other invalid
values.
"""

import typing
from typing import Any

from acb.depends import depends
from acb.logger import Logger


def ensure_logger_dependency() -> None:
    """
    Ensure that Logger and LoggerProtocol are properly registered in the DI container.
    This prevents issues where empty tuples might get registered instead of logger instances.
    """
    # Check if Logger is registered and has a valid instance
    try:
        logger_instance = depends.get_sync(Logger)
        # If we get an empty tuple, string, or other invalid value, replace it
        if isinstance(logger_instance, tuple) and len(logger_instance) == 0:
            # Log this issue for debugging
            print(
                "WARNING: Logger dependency was registered as empty tuple, replacing with fresh instance"
            )
            # Create a new logger instance to replace the invalid one
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(Logger, fresh_logger)
        elif isinstance(logger_instance, str):
            # Log this issue for debugging
            print(
                f"WARNING: Logger dependency was registered as string ({logger_instance!r}), replacing with fresh instance"
            )
            # Create a new logger instance to replace the invalid one
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(Logger, fresh_logger)
    except Exception:
        # If there's no logger registered at all, create one
        from acb.logger import Logger as ACBLogger

        fresh_logger = ACBLogger()
        depends.set(Logger, fresh_logger)

    # Do the same check for LoggerProtocol if it exists
    # Import once to avoid typing issues
    try:
        from crackerjack.models.protocols import LoggerProtocol as _LoggerProtocol

        logger_proto_instance = depends.get_sync(_LoggerProtocol)
        if isinstance(logger_proto_instance, tuple) and len(logger_proto_instance) == 0:
            # Log this issue for debugging
            print(
                "WARNING: LoggerProtocol dependency was registered as empty tuple, replacing with fresh instance"
            )
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(_LoggerProtocol, fresh_logger)
        elif isinstance(logger_proto_instance, str):
            # Log this issue for debugging
            print(
                f"WARNING: LoggerProtocol dependency was registered as string ({logger_proto_instance!r}), replacing with fresh instance"
            )
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(_LoggerProtocol, fresh_logger)
    except ImportError:
        # LoggerProtocol doesn't exist, that's fine
        pass
    except Exception:
        # If there's no LoggerProtocol registered, create one
        try:
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            print("INFO: Registering LoggerProtocol with fresh logger instance")
            # Register the fresh_logger instance with the LoggerProtocol
            depends.set(_LoggerProtocol, fresh_logger)
        except NameError:
            # _LoggerProtocol is not defined if the import failed
            pass
        except Exception:
            pass  # Any other error, just continue


def validate_dependency_registration(
    dep_type: type[Any], fallback_factory: typing.Callable | None = None
) -> bool:
    """
    Validate that a dependency is properly registered and not an empty tuple or string.

    Args:
        dep_type: The type of dependency to validate
        fallback_factory: Optional factory function to create a fallback instance if needed

    Returns:
        True if the dependency is properly registered, False otherwise
    """
    try:
        instance = depends.get_sync(dep_type)
        # Check if it's an empty tuple (the problematic case)
        if isinstance(instance, tuple) and len(instance) == 0:
            # Log this issue for debugging
            print(f"WARNING: Dependency {dep_type} was registered as empty tuple")
            # Replace with a fallback if provided
            if fallback_factory:
                fallback_instance = fallback_factory()
                depends.set(dep_type, fallback_instance)
                print(f"INFO: Replaced empty tuple for {dep_type} with new instance")
                return True
            return False
        # Check if it's a string (another problematic case)
        elif isinstance(instance, str):
            # Log this issue for debugging
            print(
                f"WARNING: Dependency {dep_type} was registered as string: {instance!r}"
            )
            # Replace with a fallback if provided
            if fallback_factory:
                fallback_instance = fallback_factory()
                depends.set(dep_type, fallback_instance)
                print(f"INFO: Replaced string for {dep_type} with new instance")
                return True
            return False
        return True
    except Exception:
        # If dependency doesn't exist at all, return False
        return False


def safe_get_logger() -> Logger:
    """
    Safely get a logger instance, ensuring it's not an empty tuple or string.

    Returns:
        A valid logger instance
    """
    try:
        logger_instance = depends.get_sync(Logger)
        if isinstance(logger_instance, tuple) and len(logger_instance) == 0:
            # Log this issue for debugging
            print(
                "WARNING: Logger dependency was an empty tuple in safe_get_logger, replacing with fresh instance"
            )
            # Create and register a fresh logger
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(Logger, fresh_logger)
            return fresh_logger
        elif isinstance(logger_instance, str):
            # Log this issue for debugging
            print(
                f"WARNING: Logger dependency was a string ({logger_instance!r}) in safe_get_logger, replacing with fresh instance"
            )
            # Create and register a fresh logger
            from acb.logger import Logger as ACBLogger

            fresh_logger = ACBLogger()
            depends.set(Logger, fresh_logger)
            return fresh_logger
        return logger_instance
    except Exception:
        # If no logger is registered, create one
        from acb.logger import Logger as ACBLogger

        print(
            "INFO: No logger registered, creating and registering a fresh logger instance"
        )
        fresh_logger = ACBLogger()
        depends.set(Logger, fresh_logger)
        return fresh_logger


def check_all_dependencies_for_empty_tuples():
    """
    Debug function to check all registered dependencies for empty tuples.
    This can help identify which dependencies have been incorrectly registered.
    """
    # This would require access to the internal state of the ACB DI system
    # which might not be available, so we'll just print a notice
    print(
        "Dependency check: To check all dependencies for empty tuples, you would need access to ACB's internal container state."
    )
    print("This is currently not possible without modifying ACB itself.")
    print(
        "The best approach is to use the individual validation functions for known problematic dependencies."
    )

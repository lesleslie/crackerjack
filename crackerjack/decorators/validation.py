"""Argument validation decorator."""

import inspect
import typing as t
from functools import wraps

from ..errors import ValidationError
from .utils import get_callable_params, is_async_function

ValidatorFunc = t.Callable[[t.Any], bool]


def validate_args(
    validators: dict[str, ValidatorFunc | list[ValidatorFunc]] | None = None,
    type_check: bool = True,
    allow_none: set[str] | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """
    Validate function arguments before execution.

    Args:
        validators: Dict mapping parameter names to validator functions or lists of validators
        type_check: Enable automatic type checking from annotations (default: True)
        allow_none: Set of parameter names that can be None even if type-checked

    Returns:
        Decorated function with argument validation

    Raises:
        ValidationError: If validation fails

    Example:
        >>> def is_positive(x: int) -> bool:
        ...     return x > 0
        >>>
        >>> @validate_args(validators={"count": is_positive})
        >>> def process_items(count: int, items: list) -> bool:
        ...     # count must be positive
        ...     return True

        >>> @validate_args(
        ...     validators={
        ...         "email": [
        ...             lambda e: "@" in e,
        ...             lambda e: len(e) > 5
        ...         ]
        ...     },
        ...     type_check=True
        ... )
        >>> async def register_user(email: str, age: int) -> bool:
        ...     # email must contain @ and be > 5 chars
        ...     # types are validated automatically
        ...     return True

    Notes:
        - Supports multiple validators per parameter
        - Type checking uses function annotations
        - Validators should return bool (True = valid)
        - Raises ValidationError with details on failure
    """
    _validators = validators or {}
    _allow_none = allow_none or set()

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        # Get function signature for validation
        sig = inspect.signature(func)
        get_callable_params(func)

        if is_async_function(func):

            @wraps(func)
            async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                # Bind arguments to parameters
                try:
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                except TypeError as e:
                    raise ValidationError(
                        message=f"Invalid arguments for {func.__name__}",
                        details=str(e),
                    ) from e

                # Validate each argument
                for param_name, param_value in bound.arguments.items():
                    _validate_parameter(
                        func,
                        param_name,
                        param_value,
                        sig.parameters[param_name],
                        _validators,
                        type_check,
                        _allow_none,
                    )

                return await func(*args, **kwargs)

            return async_wrapper

        else:

            @wraps(func)
            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                try:
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                except TypeError as e:
                    raise ValidationError(
                        message=f"Invalid arguments for {func.__name__}",
                        details=str(e),
                    ) from e

                for param_name, param_value in bound.arguments.items():
                    _validate_parameter(
                        func,
                        param_name,
                        param_value,
                        sig.parameters[param_name],
                        _validators,
                        type_check,
                        _allow_none,
                    )

                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


def _validate_parameter(
    func: t.Callable[..., t.Any],
    param_name: str,
    param_value: t.Any,
    param: inspect.Parameter,
    validators: dict[str, ValidatorFunc | list[ValidatorFunc]],
    type_check: bool,
    allow_none: set[str],
) -> None:
    """Validate a single parameter."""
    # Allow None if specified
    if param_value is None and param_name in allow_none:
        return

    # Type checking
    if type_check and param.annotation != inspect.Parameter.empty:
        if not _check_type(param_value, param.annotation, param_name in allow_none):
            raise ValidationError(
                message=f"Type validation failed for parameter '{param_name}' in {func.__name__}",
                details={
                    "parameter": param_name,
                    "expected_type": str(param.annotation),
                    "actual_type": type(param_value).__name__,
                    "value": repr(param_value),
                },
                recovery=f"Ensure {param_name} is of type {param.annotation}",
            )

    # Custom validators
    if param_name in validators:
        param_validators = validators[param_name]
        validator_list = (
            param_validators
            if isinstance(param_validators, list)
            else [param_validators]
        )

        for i, validator in enumerate(validator_list):
            try:
                if not validator(param_value):
                    raise ValidationError(
                        message=f"Validation failed for parameter '{param_name}' in {func.__name__}",
                        details={
                            "parameter": param_name,
                            "validator_index": i,
                            "value": repr(param_value),
                        },
                        recovery=f"Check the validation requirements for {param_name}",
                    )
            except Exception as e:
                if isinstance(e, ValidationError):
                    raise
                raise ValidationError(
                    message=f"Validator error for parameter '{param_name}' in {func.__name__}",
                    details={
                        "parameter": param_name,
                        "validator_index": i,
                        "error": str(e),
                    },
                ) from e


def _check_type(value: t.Any, expected_type: t.Any, allow_none: bool) -> bool:
    """Check if value matches expected type annotation."""
    # Handle None
    if value is None:
        return allow_none

    # Handle typing generics
    origin = t.get_origin(expected_type)

    if origin is not None:
        # Handle Optional[T] / Union[T, None]
        if origin is t.Union:
            args = t.get_args(expected_type)
            return any(_check_type(value, arg, allow_none) for arg in args)

        # Handle list, dict, etc.
        if origin in (list, dict, set, tuple):
            return isinstance(value, origin)

        # Other generic types - just check origin
        return isinstance(value, origin)

    # Direct type check
    if isinstance(expected_type, type):
        return isinstance(value, expected_type)

    # Can't validate complex types, assume valid
    return True

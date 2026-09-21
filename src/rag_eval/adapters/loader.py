"""Safe loading of explicitly configured local Python targets."""

import importlib
import inspect
from typing import Any

from rag_eval.adapters.errors import TargetProtocolError, TargetUnavailableError


def load_python_target(import_path: str) -> object:
    """Load and instantiate a target from a ``module:symbol`` import path.

    Only explicit import paths are accepted.  The symbol may be an already
    constructed target or a zero-argument class/factory; expressions and
    arbitrary source code are never evaluated.

    Raises:
        TargetUnavailableError: If the module or symbol cannot be loaded.
        TargetProtocolError: If the resulting object lacks core operations.
    """
    module_name, separator, symbol_name = import_path.partition(":")
    if (
        separator != ":"
        or not module_name
        or not symbol_name
        or ":" in symbol_name
        or not all(part.isidentifier() for part in module_name.split("."))
        or not symbol_name.isidentifier()
    ):
        raise TargetUnavailableError(
            "Python targets must use an explicit 'module:symbol' import path."
        )

    try:
        module = importlib.import_module(module_name)
        target = getattr(module, symbol_name)
    except (ImportError, AttributeError) as exc:
        raise TargetUnavailableError(
            f"Unable to load Python target '{import_path}'."
        ) from exc

    if inspect.isclass(target) or inspect.isfunction(target):
        try:
            target = target()
        except Exception as exc:
            raise TargetUnavailableError(
                f"Unable to instantiate Python target '{import_path}'."
            ) from exc

    _validate_core_operations(target)
    return target


def _validate_core_operations(target: object) -> None:
    """Validate the smallest callable Python-target contract at load time."""
    missing = [
        operation
        for operation in ("capabilities", "query")
        if not callable(getattr(target, operation, None))
    ]
    if missing:
        raise TargetProtocolError(
            "Python target is missing required core operation(s): "
            f"{', '.join(missing)}.",
            operation="load",
        )


def target_method(target: object, operation: str) -> Any:
    """Return a callable target operation or raise a normalized protocol error."""
    method = getattr(target, operation, None)
    if not callable(method):
        raise TargetProtocolError(
            f"Target advertised '{operation}' but does not implement it.",
            operation=operation,
        )
    return method

"""Canonical adapters for invoking evaluated targets."""

from rag_eval.adapters.base import DocumentContent, DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    TargetUnavailableError,
    UnsupportedCapabilityError,
)
from rag_eval.adapters.loader import load_python_target
from rag_eval.adapters.python import PythonTargetAdapter
from rag_eval.config.models import TargetConfig


def create_target_adapter(config: TargetConfig) -> TargetAdapter:
    """Create the configured transport adapter without executing target work.

    Only the local Python transport is available in this stage.  The explicit
    branch keeps a future HTTP implementation isolated from execution code.
    """
    if config.adapter != "python":
        raise ValueError(f"Target adapter '{config.adapter}' is not available yet.")
    if config.python_target is None:
        raise ValueError("Python target configuration requires python_target.")
    return PythonTargetAdapter(load_python_target(config.python_target))


__all__ = [
    "DocumentContent",
    "DocumentUpload",
    "PythonTargetAdapter",
    "TargetAdapter",
    "TargetAdapterError",
    "TargetProtocolError",
    "TargetUnavailableError",
    "UnsupportedCapabilityError",
    "create_target_adapter",
    "load_python_target",
]

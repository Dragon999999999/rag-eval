"""Canonical adapters for invoking evaluated targets."""

from rag_eval.adapters.base import DocumentContent, DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    TargetUnavailableError,
    UnsupportedCapabilityError,
)
from rag_eval.adapters.http import HttpTargetAdapter, TransportMetadata
from rag_eval.adapters.loader import load_python_target
from rag_eval.adapters.python import PythonTargetAdapter
from rag_eval.config.loader import resolve_environment_reference
from rag_eval.config.models import TargetConfig


def create_target_adapter(config: TargetConfig) -> TargetAdapter:
    """Create the configured transport adapter without executing target work.

    The explicit transport branches keep execution code independent of target
    implementation details.
    """
    if config.adapter == "python":
        if config.python_target is None:
            raise ValueError("Python target configuration requires python_target.")
        return PythonTargetAdapter(load_python_target(config.python_target))
    if config.base_url is None:
        raise ValueError("HTTP target configuration requires base_url.")
    token = (
        resolve_environment_reference(config.authentication_env)
        if config.authentication_env is not None
        else None
    )
    return HttpTargetAdapter(str(config.base_url), bearer_token=token)


__all__ = [
    "DocumentContent",
    "DocumentUpload",
    "HttpTargetAdapter",
    "PythonTargetAdapter",
    "TargetAdapter",
    "TargetAdapterError",
    "TargetProtocolError",
    "TargetUnavailableError",
    "TransportMetadata",
    "UnsupportedCapabilityError",
    "create_target_adapter",
    "load_python_target",
]

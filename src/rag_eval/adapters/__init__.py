"""Canonical adapters for invoking evaluated targets."""

from rag_eval.adapters.base import (
    DocumentContent,
    DocumentUpload,
    ResolvedTargetCredentials,
    TargetAdapter,
)
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    TargetUnavailableError,
    UnsupportedCapabilityError,
)
from rag_eval.adapters.factory import (
    create_target_adapter,
    get_target_adapter_registration,
    register_target_adapter,
    registered_target_adapters,
    target_adapter_descriptors,
)
from rag_eval.adapters.http import (
    HttpTargetAdapter,
    TransportMetadata,
)
from rag_eval.adapters.generic_http import GenericHttpTargetAdapter
from rag_eval.adapters.openai_compatible import OpenAICompatibleAdapter
from rag_eval.adapters.loader import load_python_target
from rag_eval.adapters.python import PythonTargetAdapter
from rag_eval.adapters.uploaded_python import (
    UploadedPythonAdapterError,
    load_uploaded_python_adapter,
    validate_uploaded_python_source,
)

__all__ = [
    "DocumentContent",
    "DocumentUpload",
    "HttpTargetAdapter",
    "GenericHttpTargetAdapter",
    "OpenAICompatibleAdapter",
    "PythonTargetAdapter",
    "ResolvedTargetCredentials",
    "TargetAdapter",
    "TargetAdapterError",
    "TargetProtocolError",
    "TargetUnavailableError",
    "TransportMetadata",
    "UnsupportedCapabilityError",
    "create_target_adapter",
    "get_target_adapter_registration",
    "load_python_target",
    "register_target_adapter",
    "registered_target_adapters",
    "target_adapter_descriptors",
    "UploadedPythonAdapterError",
    "load_uploaded_python_adapter",
    "validate_uploaded_python_source",
]
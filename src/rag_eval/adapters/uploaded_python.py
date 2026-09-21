"""Loading of trusted user-supplied Python target adapters.

Level-4 target integration allows a user to upload a Python module instead of
providing target.yaml.

The uploaded module must expose:

    def create_adapter() -> TargetAdapter:
        ...

The returned object must implement the canonical TargetAdapter interface.

IMPORTANT:
    Uploaded Python adapters execute arbitrary Python code in the rag-eval
    process. This mechanism is intended only for trusted adapter source code.
    It is not a sandbox.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from types import ModuleType
from typing import cast

from rag_eval.adapters.base import TargetAdapter


ENTRYPOINT = "create_adapter"


_REQUIRED_METHODS = (
    "capabilities",
    "health",
    "create_corpus",
    "get_corpus",
    "delete_corpus",
    "upload_document",
    "upload_chunks",
    "get_operation",
    "retrieve",
    "query",
    "stream_query",
    "recover_request",
    "aclose",
)


class UploadedPythonAdapterError(RuntimeError):
    """Raised when an uploaded Python adapter cannot be loaded."""


def validate_uploaded_python_source(
    source: bytes,
    *,
    filename: str = "target_adapter.py",
) -> None:
    """Validate Python syntax without executing uploaded code."""

    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadedPythonAdapterError(
            "Uploaded Python adapter must contain UTF-8 source code."
        ) from exc

    try:
        compile(
            text,
            filename,
            "exec",
        )
    except SyntaxError as exc:
        raise UploadedPythonAdapterError(
            f"Uploaded Python adapter contains invalid syntax: {exc}"
        ) from exc


def load_uploaded_python_adapter(
    source: bytes,
    *,
    filename: str = "target_adapter.py",
) -> TargetAdapter:
    """Execute trusted adapter source and return its TargetAdapter instance."""

    validate_uploaded_python_source(
        source,
        filename=filename,
    )

    text = source.decode("utf-8")

    source_hash = hashlib.sha256(
        source
    ).hexdigest()[:16]

    module_name = (
        f"rag_eval_uploaded_adapter_{source_hash}"
    )

    module = ModuleType(
        module_name
    )

    module.__file__ = filename
    module.__package__ = None

    try:
        code = compile(
            text,
            filename,
            "exec",
        )

        exec(
            code,
            module.__dict__,
        )

    except Exception as exc:
        raise UploadedPythonAdapterError(
            f"Failed to execute uploaded adapter '{filename}'."
        ) from exc

    factory = getattr(
        module,
        ENTRYPOINT,
        None,
    )

    if not callable(factory):
        raise UploadedPythonAdapterError(
            f"Uploaded adapter must define "
            f"`def {ENTRYPOINT}() -> TargetAdapter`."
        )

    try:
        adapter = factory()

    except Exception as exc:
        raise UploadedPythonAdapterError(
            f"Uploaded adapter entrypoint '{ENTRYPOINT}' failed."
        ) from exc

    _validate_adapter_interface(
        adapter
    )

    return cast(
        TargetAdapter,
        adapter,
    )


def _validate_adapter_interface(
    adapter: object,
) -> None:
    """Check the structural TargetAdapter contract."""

    missing: list[str] = []

    for name in _REQUIRED_METHODS:
        member = getattr(
            adapter,
            name,
            None,
        )

        if not callable(member):
            missing.append(
                name
            )

    if missing:
        joined = ", ".join(
            missing
        )

        raise UploadedPythonAdapterError(
            "Uploaded adapter does not implement the complete "
            f"TargetAdapter interface. Missing: {joined}."
        )
"""Execution-related models for run lifecycle management."""

from pydantic import Field

from rag_eval.models.common import CanonicalModel, JsonDict


class RunExecutionMode(CanonicalModel):
    """Execution mode configuration for a run.

    This is a placeholder for future execution mode configuration.
    Currently only supports standard QUERY execution.
    """

    mode: str = "QUERY"
    retrieval_only: bool = False

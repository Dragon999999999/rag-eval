"""rag-eval HTTP API package.

Provides REST API endpoints for managing targets, benchmarks,
metric configurations, test definitions, and evaluation runs.
"""

from rag_eval.api.app import app

__all__ = ["app"]

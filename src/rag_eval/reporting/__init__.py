"""Reporting and export services for rag-eval.

This package provides:
- Human-readable report generation
- Run comparison
- Portable Parquet exports
- Summary JSON generation

All reporting operates on persisted data only.
"""

from .compare import RunComparator, ComparisonResult
from .export import ExportService, ExportedRun
from .summary import ReportGenerator, RunReport

__all__ = [
    "RunComparator",
    "ComparisonResult",
    "ExportService",
    "ExportedRun",
    "ReportGenerator",
    "RunReport",
]

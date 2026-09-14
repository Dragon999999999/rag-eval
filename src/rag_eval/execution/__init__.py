"""Benchmark execution engine for rag-eval.

This package coordinates end-to-end benchmark execution:

```text
load configuration
→ create run
→ execute cases with bounded concurrency
→ persist every result durably
→ finish run
```
"""

from .engine import BenchmarkExecutor, ExecutionConfig, ExecutionResult
from .observation import ObservationNormalizer
from .requests import RequestIdentity, RequestIdentityGenerator
from .timing import ClientTiming

__all__ = [
    "BenchmarkExecutor",
    "ExecutionConfig",
    "ExecutionResult",
    "ObservationNormalizer",
    "RequestIdentity",
    "RequestIdentityGenerator",
    "ClientTiming",
]

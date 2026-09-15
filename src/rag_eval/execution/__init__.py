"""Benchmark execution engine for rag-eval.

This package coordinates end-to-end benchmark execution:

```text
load configuration
→ create run
→ execute cases with bounded concurrency
→ persist every result durably
→ finish run
```

Stage 10 adds retry, recovery, circuit breaker, and resume support.
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from .engine import BenchmarkExecutor, ExecutionConfig, ExecutionResult
from .observation import ObservationNormalizer
from .recovery import CaseRecoveryService, RecoveryAction, RecoveryDecision
from .requests import RequestIdentity, RequestIdentityGenerator
from .retry import RetryDecision, RetryPolicy
from .timing import ClientTiming
from .worker import CaseExecutionResult, ResilientCaseWorker

__all__ = [
    "BenchmarkExecutor",
    "CaseExecutionResult",
    "CaseRecoveryService",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "ExecutionConfig",
    "ExecutionResult",
    "ObservationNormalizer",
    "RecoveryAction",
    "RecoveryDecision",
    "RequestIdentity",
    "RequestIdentityGenerator",
    "ResilientCaseWorker",
    "RetryDecision",
    "RetryPolicy",
    "ClientTiming",
]

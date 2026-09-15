"""Performance and latency metrics for Stage 12.

Deterministic metrics measuring execution timing from trace data.
No LLM judges or external calls.

Metrics:
- total_latency: End-to-end execution time
- retrieval_latency: Time spent in retrieval
- generation_latency: Time spent in generation
- tokens_per_second: Throughput metric
"""

from dataclasses import dataclass, field
from typing import Any

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext
from rag_eval.metrics.helpers import safe_divide


def _extract_timing_from_trace(trace: dict[str, Any]) -> dict[str, float]:
    """Extract timing information from execution trace.

    Args:
        trace: Execution trace with timing data.

    Returns:
        Dictionary with timing values in seconds.
    """
    timings = {}

    # Handle hierarchical trace with spans
    spans = trace.get("spans", [])
    if spans:
        total_ms = 0.0
        stage_times = {}

        for span in spans:
            span_name = span.get("name", "unknown")
            duration = span.get("duration_ms")
            if duration is not None:
                stage_times[f"{span_name}_ms"] = duration
                total_ms += duration

        if total_ms > 0:
            timings["total_ms"] = total_ms
        timings.update(stage_times)
    else:
        # Look for explicit timing fields
        if "duration_ms" in trace:
            timings["total_ms"] = trace["duration_ms"]
        elif "duration_s" in trace:
            timings["total_s"] = trace["duration_s"]
        elif "start_time_ms" in trace and "end_time_ms" in trace:
            timings["total_ms"] = trace["end_time_ms"] - trace["start_time_ms"]
        elif "start_time_s" in trace and "end_time_s" in trace:
            timings["total_s"] = trace["end_time_s"] - trace["start_time_s"]

        # Look for stage-specific timings
        stages = trace.get("stages", [])
        for stage in stages:
            stage_name = stage.get("name", "unknown")
            if "duration_ms" in stage:
                timings[f"{stage_name}_ms"] = stage["duration_ms"]
            elif "duration_s" in stage:
                timings[f"{stage_name}_s"] = stage["duration_s"]

    return timings


@dataclass
class TotalLatencyResult(MetricResult):
    """Result of total latency computation."""

    metric_id: str = field(init=False, default="performance.total_latency_ms")
    metric_version: str = field(init=False, default="1")


class TotalLatency:
    """Total Latency: End-to-end execution time in milliseconds.

    Extracts timing from execution trace.
    Returns milliseconds for consistency.

    Formula:
        latency = end_time - start_time

    Requirements:
        - TRACE: Target must produce execution trace with timing

    Edge cases:
        - No trace → UNAVAILABLE_MISSING_INPUT
        - No timing data → UNAVAILABLE_MISSING_INPUT
        - Negative latency → FAILED (invalid data)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="performance.total_latency_ms",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.TRACE}),
            description="End-to-end execution time in milliseconds.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check trace
        if not context.has_trace():
            return TotalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no execution trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.trace is None:
            return TotalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        trace = observation.trace.model_dump(mode="json")
        timings = _extract_timing_from_trace(trace)

        # Extract total latency
        total_ms = timings.get("total_ms")
        if total_ms is None:
            total_s = timings.get("total_s")
            if total_s is not None:
                total_ms = total_s * 1000

        if total_ms is None:
            return TotalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No timing data in trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"trace_keys": list(trace.keys())},
            )

        # Validate
        if total_ms < 0:
            return TotalLatencyResult(
                status=MetricStatus.FAILED,
                reason=f"Negative latency: {total_ms}ms",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"total_ms": total_ms},
            )

        return TotalLatencyResult(
            status=MetricStatus.COMPUTED,
            value=round(total_ms, 3),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "total_ms": round(total_ms, 3),
                "timing_keys": list(timings.keys()),
            },
        )


@dataclass
class RetrievalLatencyResult(MetricResult):
    """Result of retrieval latency computation."""

    metric_id: str = field(init=False, default="performance.retrieval_latency_ms")
    metric_version: str = field(init=False, default="1")


class RetrievalLatency:
    """Retrieval Latency: Time spent in retrieval stage.

    Extracts retrieval-specific timing from trace.

    Formula:
        retrieval_latency = retrieval_end - retrieval_start

    Requirements:
        - TRACE: Target must produce execution trace with stage timings

    Edge cases:
        - No trace → UNAVAILABLE_MISSING_INPUT
        - No retrieval timing → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="performance.retrieval_latency_ms",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.TRACE}),
            description="Time spent in retrieval stage in milliseconds.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check trace
        if not context.has_trace():
            return RetrievalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no execution trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.trace is None:
            return RetrievalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        trace = observation.trace.model_dump(mode="json")
        timings = _extract_timing_from_trace(trace)

        # Look for retrieval timing
        retrieval_ms = None
        for key in ["retrieval_ms", "retrieve_ms", "candidate_retrieval_ms"]:
            if key in timings:
                retrieval_ms = timings[key]
                break

        if retrieval_ms is None:
            # Try seconds
            for key in ["retrieval_s", "retrieve_s", "candidate_retrieval_s"]:
                if key in timings:
                    retrieval_ms = timings[key] * 1000
                    break

        if retrieval_ms is None:
            return RetrievalLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No retrieval timing in trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"timing_keys": list(timings.keys())},
            )

        # Validate
        if retrieval_ms < 0:
            return RetrievalLatencyResult(
                status=MetricStatus.FAILED,
                reason=f"Negative latency: {retrieval_ms}ms",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"retrieval_ms": retrieval_ms},
            )

        return RetrievalLatencyResult(
            status=MetricStatus.COMPUTED,
            value=round(retrieval_ms, 3),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"retrieval_ms": round(retrieval_ms, 3)},
        )


@dataclass
class GenerationLatencyResult(MetricResult):
    """Result of generation latency computation."""

    metric_id: str = field(init=False, default="performance.generation_latency_ms")
    metric_version: str = field(init=False, default="1")


class GenerationLatency:
    """Generation Latency: Time spent in answer generation.

    Extracts generation-specific timing from trace.

    Formula:
        generation_latency = generation_end - generation_start

    Requirements:
        - TRACE: Target must produce execution trace with stage timings

    Edge cases:
        - No trace → UNAVAILABLE_MISSING_INPUT
        - No generation timing → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="performance.generation_latency_ms",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.TRACE}),
            description="Time spent in answer generation in milliseconds.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check trace
        if not context.has_trace():
            return GenerationLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no execution trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.trace is None:
            return GenerationLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        trace = observation.trace.model_dump(mode="json")
        timings = _extract_timing_from_trace(trace)

        # Look for generation timing
        gen_ms = None
        for key in ["generation_ms", "generate_ms", "answer_ms", "llm_ms"]:
            if key in timings:
                gen_ms = timings[key]
                break

        if gen_ms is None:
            # Try seconds
            for key in ["generation_s", "generate_s", "answer_s", "llm_s"]:
                if key in timings:
                    gen_ms = timings[key] * 1000
                    break

        if gen_ms is None:
            return GenerationLatencyResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No generation timing in trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"timing_keys": list(timings.keys())},
            )

        # Validate
        if gen_ms < 0:
            return GenerationLatencyResult(
                status=MetricStatus.FAILED,
                reason=f"Negative latency: {gen_ms}ms",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"generation_ms": gen_ms},
            )

        return GenerationLatencyResult(
            status=MetricStatus.COMPUTED,
            value=round(gen_ms, 3),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"generation_ms": round(gen_ms, 3)},
        )


@dataclass
class TokensPerSecondResult(MetricResult):
    """Result of tokens-per-second computation."""

    metric_id: str = field(init=False, default="performance.tokens_per_second")
    metric_version: str = field(init=False, default="1")


class TokensPerSecond:
    """Tokens Per Second: Generation throughput.

    Formula:
        throughput = generated_tokens / generation_time_seconds

    Requirements:
        - TRACE: Target must produce execution trace
        - USAGE: Target must report token usage

    Edge cases:
        - No usage data → UNAVAILABLE_MISSING_INPUT
        - No timing data → UNAVAILABLE_MISSING_INPUT
        - Zero generation time → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="performance.tokens_per_second",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.TRACE, MetricRequirement.USAGE}),
            description="Generation throughput in tokens per second.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check trace
        if not context.has_trace():
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no execution trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage or trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        trace = observation.trace.model_dump(mode="json")

        # Get generated tokens
        generated_tokens = usage.get("generated_tokens") or usage.get(
            "completion_tokens"
        )
        if generated_tokens is None:
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No generated tokens in usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"usage_keys": list(usage.keys())},
            )

        # Get generation timing
        timings = _extract_timing_from_trace(trace)
        gen_s = None

        for key in ["generation_s", "generate_s", "generation_ms"]:
            if key in timings:
                value = timings[key]
                if key.endswith("_ms"):
                    gen_s = value / 1000
                else:
                    gen_s = value
                break

        if gen_s is None:
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No generation timing in trace",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"timing_keys": list(timings.keys())},
            )

        if gen_s <= 0:
            return TokensPerSecondResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason=f"Invalid generation time: {gen_s}s",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"generation_s": gen_s},
            )

        throughput = safe_divide(generated_tokens, gen_s, default=0.0)

        return TokensPerSecondResult(
            status=MetricStatus.COMPUTED,
            value=round(throughput, 3),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "generated_tokens": generated_tokens,
                "generation_s": round(gen_s, 4),
                "tokens_per_second": round(throughput, 3),
            },
        )


# Export all performance metrics
__all__ = [
    "TotalLatency",
    "RetrievalLatency",
    "GenerationLatency",
    "TokensPerSecond",
]

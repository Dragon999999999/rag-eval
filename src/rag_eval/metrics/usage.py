"""Usage and cost metrics for Stage 12.

Deterministic metrics measuring resource consumption and cost.
No LLM judges or external calls.

Metrics:
- total_tokens: Sum of input and output tokens
- input_tokens: Tokens in prompts/requests
- output_tokens: Tokens in completions/responses
- total_cost: Monetary cost based on pricing
- cost_per_token: Average cost efficiency
"""

from dataclasses import dataclass, field
from typing import Any, TypedDict

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext
from rag_eval.metrics.helpers import format_currency, safe_divide


class UsageValues(TypedDict):
    input_tokens: int | float
    output_tokens: int | float
    total_tokens: int | float
    cost: int | float
    currency: str


def _extract_usage_values(usage: dict[str, Any]) -> UsageValues:
    """Extract numeric values from usage data."""

    values: UsageValues = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
        "currency": "USD",
    }

    tokens = usage.get("tokens", {})
    if isinstance(tokens, dict):
        values["input_tokens"] = tokens.get("input", 0)
        values["output_tokens"] = tokens.get("output", 0)
        values["total_tokens"] = tokens.get("total", 0)
    else:
        values["input_tokens"] = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or usage.get("request_tokens")
            or 0
        )
        values["output_tokens"] = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or usage.get("response_tokens")
            or 0
        )

        explicit_total = usage.get("total_tokens")
        if explicit_total is not None:
            values["total_tokens"] = explicit_total
        else:
            values["total_tokens"] = (
                values["input_tokens"] + values["output_tokens"]
            )

    cost_data = usage.get("cost", {})
    if isinstance(cost_data, dict):
        values["cost"] = cost_data.get("total", 0.0)

        currency = cost_data.get("currency", "USD")
        values["currency"] = currency if isinstance(currency, str) else "USD"
    else:
        values["cost"] = usage.get("cost") or usage.get("total_cost") or 0.0

        currency = usage.get("currency", "USD")
        values["currency"] = currency if isinstance(currency, str) else "USD"

    return values

@dataclass
class TotalTokensResult(MetricResult):
    """Result of total tokens computation."""

    metric_id: str = field(init=False, default="usage.total_tokens")
    metric_version: str = field(init=False, default="1")


class TotalTokens:
    """Total Tokens: Sum of all tokens consumed.

    Formula:
        total = input_tokens + output_tokens

    Requirements:
        - USAGE: Target must report usage data

    Edge cases:
        - No usage → UNAVAILABLE_MISSING_INPUT
        - Zero tokens → 0 (valid, e.g., empty response)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="usage.total_tokens",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.USAGE}),
            description="Total tokens consumed (input + output).",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return TotalTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return TotalTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        values = _extract_usage_values(usage)

        return TotalTokensResult(
            status=MetricStatus.COMPUTED,
            value=values["total_tokens"],
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "input_tokens": values["input_tokens"],
                "output_tokens": values["output_tokens"],
                "total_tokens": values["total_tokens"],
            },
        )


@dataclass
class InputTokensResult(MetricResult):
    """Result of input tokens computation."""

    metric_id: str = field(init=False, default="usage.input_tokens")
    metric_version: str = field(init=False, default="1")


class InputTokens:
    """Input Tokens: Tokens in prompts/requests.

    Requirements:
        - USAGE: Target must report usage data

    Edge cases:
        - No usage → UNAVAILABLE_MISSING_INPUT
        - Zero input tokens → 0 (valid)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="usage.input_tokens",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.USAGE}),
            description="Tokens in input prompts.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return InputTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return InputTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        values = _extract_usage_values(usage)

        return InputTokensResult(
            status=MetricStatus.COMPUTED,
            value=values["input_tokens"],
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"input_tokens": values["input_tokens"]},
        )


@dataclass
class OutputTokensResult(MetricResult):
    """Result of output tokens computation."""

    metric_id: str = field(init=False, default="usage.output_tokens")
    metric_version: str = field(init=False, default="1")


class OutputTokens:
    """Output Tokens: Tokens in completions/responses.

    Requirements:
        - USAGE: Target must report usage data

    Edge cases:
        - No usage → UNAVAILABLE_MISSING_INPUT
        - Zero output tokens → 0 (valid)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="usage.output_tokens",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.USAGE}),
            description="Tokens in output completions.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return OutputTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return OutputTokensResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        values = _extract_usage_values(usage)

        return OutputTokensResult(
            status=MetricStatus.COMPUTED,
            value=values["output_tokens"],
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"output_tokens": values["output_tokens"]},
        )


@dataclass
class TotalCostResult(MetricResult):
    """Result of total cost computation."""

    metric_id: str = field(init=False, default="cost.total")
    metric_version: str = field(init=False, default="1")


class TotalCost:
    """Total Cost: Monetary cost of the request.

    Uses cost from usage data if available.
    If no explicit cost, returns UNAVAILABLE_MISSING_INPUT.

    Formula:
        cost = usage.cost (from target)

    Requirements:
        - USAGE: Target must report usage data with cost

    Edge cases:
        - No usage → UNAVAILABLE_MISSING_INPUT
        - No cost field → UNAVAILABLE_MISSING_INPUT
        - Zero cost → 0.0 (valid, e.g., free tier)
    """

    def __init__(self, currency: str = "USD") -> None:
        self._currency = currency
        self._definition = MetricDefinition(
            metric_id="cost.total",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.USAGE}),
            description=f"Total monetary cost in {currency}.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return TotalCostResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return TotalCostResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        values = _extract_usage_values(usage)

        # Check if cost was explicitly provided (not just default empty dict)
        cost_data = usage.get("cost")
        if not cost_data or not isinstance(cost_data, dict) or "total" not in cost_data:
            return TotalCostResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No cost information in usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"usage_keys": list(usage.keys())},
            )

        cost = values.get("cost", 0.0)
        currency = values.get("currency", self._currency)

        return TotalCostResult(
            status=MetricStatus.COMPUTED,
            value=round(cost, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "cost": round(cost, 6),
                "currency": currency,
                "formatted": format_currency(cost, currency),
            },
        )


@dataclass
class CostPerTokenResult(MetricResult):
    """Result of cost-per-token computation."""

    metric_id: str = field(init=False, default="cost.per_token")
    metric_version: str = field(init=False, default="1")


class CostPerToken:
    """Cost Per Token: Average cost efficiency.

    Formula:
        cost_per_token = total_cost / total_tokens

    Requirements:
        - USAGE: Target must report usage data with cost and tokens

    Edge cases:
        - No cost data → UNAVAILABLE_MISSING_INPUT
        - Zero tokens → UNAVAILABLE_MISSING_INPUT (cannot divide)
    """

    def __init__(self, currency: str = "USD") -> None:
        self._currency = currency
        self._definition = MetricDefinition(
            metric_id="cost.per_token",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.USAGE}),
            description=f"Average cost per token in {currency}.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check usage
        if not context.has_usage():
            return CostPerTokenResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        observation = context.observation
        if observation is None or observation.usage is None:
            return CostPerTokenResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        usage = observation.usage.model_dump(mode="json")
        values = _extract_usage_values(usage)

        cost = values.get("cost")
        if cost is None:
            return CostPerTokenResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="No cost information in usage data",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        total_tokens = values.get("total_tokens", 0)
        if total_tokens == 0:
            return CostPerTokenResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Zero tokens (cannot compute cost per token)",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"cost": cost, "total_tokens": total_tokens},
            )

        cost_per_token = safe_divide(cost, total_tokens, default=0.0)
        currency = values.get("currency", self._currency)

        return CostPerTokenResult(
            status=MetricStatus.COMPUTED,
            value=round(cost_per_token, 10),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "cost": round(cost, 6),
                "total_tokens": total_tokens,
                "cost_per_token": round(cost_per_token, 10),
                "currency": currency,
                "formatted": f"{format_currency(cost_per_token, currency)} / token",
            },
        )


# Export all usage and cost metrics
__all__ = [
    "TotalTokens",
    "InputTokens",
    "OutputTokens",
    "TotalCost",
    "CostPerToken",
]

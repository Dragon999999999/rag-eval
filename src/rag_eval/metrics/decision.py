"""Decision, abstention, and answerability metrics."""

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext
from rag_eval.models.enums import Answerability, DecisionAction


class _DecisionMetric:
    """Base for per-case decision metrics."""

    metric_id: str
    description: str

    def __init__(self, requirements: frozenset[MetricRequirement]) -> None:
        self._definition = MetricDefinition(
            metric_id=self.metric_id,
            version="1",
            scope=MetricScope.CASE,
            requirements=requirements,
            description=self.description,
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    def _decision(self, context: MetricContext) -> DecisionAction | None:
        return context.observation.decision.action if context.has_decision() else None

    def _result(
        self,
        context: MetricContext,
        value: float | None,
        *,
        reason: str | None = None,
    ) -> MetricResult:
        return MetricResult(
            metric_id=self.metric_id,
            metric_version="1",
            status=(
                MetricStatus.COMPUTED
                if reason is None
                else MetricStatus.UNAVAILABLE_MISSING_INPUT
            ),
            value=value,
            reason=reason,
            case_id=context.case.case_id,
            run_id=context.run_id,
        )


class _ActionRate(_DecisionMetric):
    action: DecisionAction

    def __init__(self, action: DecisionAction) -> None:
        self.action = action
        super().__init__(frozenset({MetricRequirement.DECISION}))

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        if action is None:
            return self._result(context, None, reason="Target decision is missing")
        return self._result(context, float(action == self.action))


class AcceptRate(_ActionRate):
    """Whether the target accepted the answer."""

    metric_id = "decision.accept_rate"
    description = "Per-case accepted-decision indicator."

    def __init__(self) -> None:
        super().__init__(DecisionAction.ACCEPT)


class RejectRate(_ActionRate):
    """Whether the target rejected the answer."""

    metric_id = "decision.reject_rate"
    description = "Per-case rejected-decision indicator."

    def __init__(self) -> None:
        super().__init__(DecisionAction.REJECT)


class AbstentionRate(_ActionRate):
    """Whether the target abstained."""

    metric_id = "decision.abstention_rate"
    description = "Per-case abstention indicator."

    def __init__(self) -> None:
        super().__init__(DecisionAction.ABSTAIN)


class AnswerabilityAccuracy(_DecisionMetric):
    """Compare accept/reject decisions to benchmark answerability."""

    metric_id = "decision.answerability_accuracy"
    description = "Agreement between decision action and benchmark answerability."

    def __init__(self) -> None:
        super().__init__(
            frozenset({MetricRequirement.DECISION, MetricRequirement.ANSWERABILITY})
        )

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        answerability = context.case.answerability
        if action is None or answerability is None:
            return self._result(
                context, None, reason="Decision or answerability is missing"
            )
        expected = (
            DecisionAction.ACCEPT
            if answerability == Answerability.ANSWERABLE
            else DecisionAction.REJECT
            if answerability == Answerability.UNANSWERABLE
            else None
        )
        if expected is None:
            return self._result(context, None, reason="Answerability is ambiguous")
        return self._result(context, float(action == expected))


class FalseAnswerRate(_DecisionMetric):
    """Flag accepted answers for unanswerable cases."""

    metric_id = "decision.false_answer_rate"
    description = "False-answer indicator for accepted unanswerable cases."

    def __init__(self) -> None:
        super().__init__(
            frozenset({MetricRequirement.DECISION, MetricRequirement.ANSWERABILITY})
        )

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        answerability = context.case.answerability
        if action is None or answerability is None:
            return self._result(
                context, None, reason="Decision or answerability is missing"
            )
        return self._result(
            context,
            float(
                action == DecisionAction.ACCEPT
                and answerability == Answerability.UNANSWERABLE
            ),
        )


class FalseAbstentionRate(_DecisionMetric):
    """Flag abstentions for answerable cases."""

    metric_id = "decision.false_abstention_rate"
    description = "False-abstention indicator for answerable cases."

    def __init__(self) -> None:
        super().__init__(
            frozenset({MetricRequirement.DECISION, MetricRequirement.ANSWERABILITY})
        )

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        answerability = context.case.answerability
        if action is None or answerability is None:
            return self._result(
                context, None, reason="Decision or answerability is missing"
            )
        return self._result(
            context,
            float(
                action == DecisionAction.ABSTAIN
                and answerability == Answerability.ANSWERABLE
            ),
        )


class AbstentionPrecision(_DecisionMetric):
    """Measure whether an abstention corresponds to an unanswerable case."""

    metric_id = "decision.abstention_precision"
    description = "Precision of abstentions for unanswerable cases."

    def __init__(self) -> None:
        super().__init__(
            frozenset({MetricRequirement.DECISION, MetricRequirement.ANSWERABILITY})
        )

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        answerability = context.case.answerability
        if action is None or answerability is None:
            return self._result(
                context, None, reason="Decision or answerability is missing"
            )
        if action != DecisionAction.ABSTAIN:
            return self._result(context, None, reason="Case was not an abstention")
        return self._result(
            context,
            float(answerability == Answerability.UNANSWERABLE),
        )


class AbstentionRecall(AbstentionPrecision):
    """Measure whether unanswerable cases receive abstentions."""

    metric_id = "decision.abstention_recall"
    description = "Recall of abstentions for unanswerable cases."

    async def compute(self, context: MetricContext) -> MetricResult:
        action = self._decision(context)
        answerability = context.case.answerability
        if action is None or answerability is None:
            return self._result(
                context, None, reason="Decision or answerability is missing"
            )
        if answerability != Answerability.UNANSWERABLE:
            return self._result(context, None, reason="Case was not unanswerable")
        return self._result(context, float(action == DecisionAction.ABSTAIN))


__all__ = [
    "AcceptRate",
    "RejectRate",
    "AbstentionRate",
    "AnswerabilityAccuracy",
    "FalseAnswerRate",
    "FalseAbstentionRate",
    "AbstentionPrecision",
    "AbstentionRecall",
]

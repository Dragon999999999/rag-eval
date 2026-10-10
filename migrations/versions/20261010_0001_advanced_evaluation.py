"""Persist advanced benchmark annotations and semantic judge results.

Revision ID: 20261010_0001
Revises: 20261005_0001
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261010_0001"
down_revision: str | None = "20261005_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_column(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=nullable,
        server_default=sa.text("'[]'::jsonb") if not nullable else None,
    )


def upgrade() -> None:
    """Add benchmark truth fields and the judge-result persistence boundary."""
    for column in (
        _json_column("reference_answers"),
        _json_column("required_facts"),
        _json_column("forbidden_facts"),
        _json_column("gold_evidence_groups"),
        _json_column("required_evidence_relations"),
        _json_column("hard_negatives"),
    ):
        op.add_column("benchmark_cases", column)
    op.add_column(
        "benchmark_cases",
        sa.Column("expected_route", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "benchmark_cases",
        sa.Column(
            "expected_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "benchmark_cases",
        sa.Column("conversation_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "benchmark_cases",
        sa.Column("turn_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "benchmark_cases",
        sa.Column("domain", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_benchmark_cases_conversation_id",
        "benchmark_cases",
        ["conversation_id"],
    )

    op.create_table(
        "judge_results",
        sa.Column("judge_result_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=128),
            sa.ForeignKey("runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_run_id",
            sa.String(length=128),
            sa.ForeignKey("metric_runs.metric_run_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "case_execution_id",
            sa.String(length=128),
            sa.ForeignKey("case_executions.case_execution_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("metric_id", sa.String(length=255), nullable=False),
        sa.Column("metric_version", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        _json_column("evidence_ids"),
        _json_column("claim_ids"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("judge_model", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=128), nullable=True),
        sa.Column(
            "usage",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("cache_key", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_judge_results_run_id", "judge_results", ["run_id"])
    op.create_index(
        "ix_judge_results_metric_run_id", "judge_results", ["metric_run_id"]
    )
    op.create_index(
        "ix_judge_results_case_execution_id",
        "judge_results",
        ["case_execution_id"],
    )
    op.create_index("ix_judge_results_metric_id", "judge_results", ["metric_id"])
    op.create_index("ix_judge_results_status", "judge_results", ["status"])
    op.create_index("ix_judge_results_cache_key", "judge_results", ["cache_key"])


def downgrade() -> None:
    """Remove advanced judge persistence and benchmark annotation columns."""
    for index in (
        "ix_judge_results_cache_key",
        "ix_judge_results_status",
        "ix_judge_results_metric_id",
        "ix_judge_results_case_execution_id",
        "ix_judge_results_metric_run_id",
        "ix_judge_results_run_id",
    ):
        op.drop_index(index, table_name="judge_results")
    op.drop_table("judge_results")
    op.drop_index("ix_benchmark_cases_conversation_id", table_name="benchmark_cases")
    for name in (
        "domain",
        "turn_index",
        "conversation_id",
        "expected_schema",
        "expected_route",
        "hard_negatives",
        "required_evidence_relations",
        "gold_evidence_groups",
        "forbidden_facts",
        "required_facts",
        "reference_answers",
    ):
        op.drop_column("benchmark_cases", name)

"""Add isolated, repeatable metric scoring passes.

The migration is intentionally additive.  Existing run-scoped metric rows use
NULL ``metric_run_id`` and continue to be served by the legacy result APIs.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261005_0001"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create metric-run identity and attach derived results to it."""
    op.create_table(
        "metric_runs",
        sa.Column("metric_run_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=128),
            sa.ForeignKey("runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_metric_runs_run_id", "metric_runs", ["run_id"])
    op.create_index("ix_metric_runs_status", "metric_runs", ["status"])

    for table in ("metric_results", "aggregate_metric_results"):
        op.add_column(
            table,
            sa.Column(
                "metric_run_id",
                sa.String(length=128),
                sa.ForeignKey("metric_runs.metric_run_id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_metric_run_id",
            table,
            ["metric_run_id"],
        )


def downgrade() -> None:
    """Remove metric-run columns and the scoring-pass table."""
    for table in ("metric_results", "aggregate_metric_results"):
        op.drop_index(f"ix_{table}_metric_run_id", table_name=table)
        op.drop_column(table, "metric_run_id")
    op.drop_index("ix_metric_runs_status", table_name="metric_runs")
    op.drop_index("ix_metric_runs_run_id", table_name="metric_runs")
    op.drop_table("metric_runs")

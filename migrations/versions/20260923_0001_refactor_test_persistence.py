# ruff: noqa: E501
"""Refactor test persistence for embedded metric selection and resumable runs.

Revision ID: 20260923_0001
Revises: 20260921_0002
Create Date: 2026-09-23

This migration:

- moves metric selection/configuration into test definitions
- migrates existing MetricConfigRecord data into test-owned selections
- allows test definitions to exist before target/benchmark configuration
- adds explicit test readiness state
- extends runs for pause/resume/interruption/recovery workflows
- adds append-only run lifecycle events
- extends attempts with retry/recovery information

Metric definitions remain registry-backed and are not persisted here.
"""

from alembic import op
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260923_0001"
down_revision: str | None = "20260921_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate evaluation/test persistence to the new test-owned model."""

    # ------------------------------------------------------------------
    # test_definitions: allow incomplete tests and own metric configuration
    # ------------------------------------------------------------------

    op.add_column(
        "test_definitions",
        sa.Column(
            "configuration_status",
            sa.String(length=64),
            nullable=False,
            server_default="INCOMPLETE",
        ),
    )

    op.add_column(
        "test_definitions",
        sa.Column(
            "metric_selection_mode",
            sa.String(length=64),
            nullable=False,
            server_default="EXPLICIT",
        ),
    )

    op.add_column(
        "test_definitions",
        sa.Column(
            "judge_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.add_column(
        "test_definitions",
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # Existing tests were required to have both references.  New tests may be
    # created first and configured later.
    op.alter_column(
        "test_definitions",
        "target_id",
        existing_type=sa.String(length=128),
        nullable=True,
    )

    op.alter_column(
        "test_definitions",
        "benchmark_id",
        existing_type=sa.String(length=128),
        nullable=True,
    )

    # Incomplete tests do not yet have a stable runnable definition hash.
    op.alter_column(
        "test_definitions",
        "definition_hash",
        existing_type=sa.String(length=64),
        nullable=True,
    )

    # Copy the reusable MetricConfig values into the owning test before the
    # legacy relation/table is removed.
    op.execute(
        """
        UPDATE test_definitions AS td
        SET
            metric_selection_mode =
                CASE
                    WHEN mc.mode = 'all_available' THEN 'ALL_AVAILABLE'
                    ELSE 'EXPLICIT'
                END,
            judge_config = COALESCE(mc.judge_config, '{}'::jsonb),
            retrieval_config = COALESCE(mc.retrieval_config, '{}'::jsonb),
            configuration_status =
                CASE
                    WHEN td.target_id IS NOT NULL
                     AND td.benchmark_id IS NOT NULL
                     AND (
                        mc.mode = 'all_available'
                        OR jsonb_array_length(
                            COALESCE(mc.selected_metrics, '[]'::jsonb)
                        ) > 0
                     )
                    THEN 'READY'
                    ELSE 'INCOMPLETE'
                END
        FROM metric_configs AS mc
        WHERE td.metric_config_id = mc.metric_config_id
        """
    )

    # ------------------------------------------------------------------
    # test_metric_selections
    # ------------------------------------------------------------------

    op.create_table(
        "test_metric_selections",
        sa.Column(
            "test_metric_selection_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "test_definition_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "metric_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "metric_version",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["test_definition_id"],
            ["test_definitions.test_definition_id"],
            name="fk_test_metric_selections_test_definition_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "test_metric_selection_id",
        ),
        sa.UniqueConstraint(
            "test_definition_id",
            "metric_id",
            name="uq_test_metric_selection_test_metric",
        ),
    )

    op.create_index(
        "ix_test_metric_selections_test_definition_id",
        "test_metric_selections",
        ["test_definition_id"],
        unique=False,
    )

    op.create_index(
        "ix_test_metric_selections_metric_id",
        "test_metric_selections",
        ["metric_id"],
        unique=False,
    )

    # Preserve every explicitly listed metric from legacy metric configs.
    # In ALL_AVAILABLE mode these rows are informational; the service resolves
    # the authoritative applicable set when a run starts.
    op.execute(
        """
        INSERT INTO test_metric_selections (
            test_metric_selection_id,
            test_definition_id,
            metric_id,
            metric_version,
            parameters,
            enabled,
            created_at,
            updated_at
        )
        SELECT
            'tms-' || md5(
                td.test_definition_id || ':' || selected.metric_id
            ),
            td.test_definition_id,
            selected.metric_id,
            NULL,
            COALESCE(
                mc.metric_parameters -> selected.metric_id,
                '{}'::jsonb
            ),
            TRUE,
            now(),
            now()
        FROM test_definitions AS td
        JOIN metric_configs AS mc
          ON mc.metric_config_id = td.metric_config_id
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(mc.selected_metrics, '[]'::jsonb)
        ) AS selected(metric_id)
        ON CONFLICT (test_definition_id, metric_id) DO NOTHING
        """
    )

    # metric_config_id is no longer part of TestDefinition.  Dropping the
    # column removes its FK/index dependencies on PostgreSQL.
    op.drop_column(
        "test_definitions",
        "metric_config_id",
    )

    op.drop_table(
        "metric_configs",
    )

    # Defaults were needed for migration/backfill but configuration is now
    # application-owned.
    op.alter_column(
        "test_definitions",
        "configuration_status",
        server_default=None,
    )

    op.alter_column(
        "test_definitions",
        "metric_selection_mode",
        server_default=None,
    )

    op.alter_column(
        "test_definitions",
        "judge_config",
        server_default=None,
    )

    op.alter_column(
        "test_definitions",
        "retrieval_config",
        server_default=None,
    )

    # ------------------------------------------------------------------
    # runs: richer lifecycle and queryable benchmark identity
    # ------------------------------------------------------------------

    op.add_column(
        "runs",
        sa.Column(
            "benchmark_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_runs_benchmark_id_benchmarks",
        "runs",
        "benchmarks",
        ["benchmark_id"],
        ["benchmark_id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_runs_benchmark_id",
        "runs",
        ["benchmark_id"],
        unique=False,
    )

    # Backfill queryable benchmark identity for runs originating from a test.
    op.execute(
        """
        UPDATE runs AS r
        SET benchmark_id = td.benchmark_id
        FROM test_definitions AS td
        WHERE r.test_definition_id = td.test_definition_id
          AND r.benchmark_id IS NULL
        """
    )

    op.add_column(
        "runs",
        sa.Column(
            "status_reason",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "runs",
        sa.Column(
            "paused_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "runs",
        sa.Column(
            "interrupted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # run_events
    # ------------------------------------------------------------------

    op.create_table(
        "run_events",
        sa.Column(
            "run_event_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
            name="fk_run_events_run_id_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "run_event_id",
        ),
    )

    op.create_index(
        "ix_run_events_run_id",
        "run_events",
        ["run_id"],
        unique=False,
    )

    op.create_index(
        "ix_run_events_event_type",
        "run_events",
        ["event_type"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # case_executions
    # ------------------------------------------------------------------

    op.add_column(
        "case_executions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # attempts: retry/recovery information
    # ------------------------------------------------------------------

    op.add_column(
        "attempts",
        sa.Column(
            "retryable",
            sa.Boolean(),
            nullable=True,
        ),
    )

    op.add_column(
        "attempts",
        sa.Column(
            "error_summary",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "attempts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Restore the previous reusable-MetricConfig persistence model.

    Downgrade cannot represent incomplete tests because the previous schema
    required both target_id and benchmark_id.  Refuse rather than silently
    deleting or fabricating user data.
    """

    # ------------------------------------------------------------------
    # Guard against data that the old schema cannot represent
    # ------------------------------------------------------------------

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM test_definitions
                WHERE target_id IS NULL
                   OR benchmark_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade: incomplete test definitions exist '
                    '(target_id or benchmark_id is NULL).';
            END IF;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # attempts / case executions
    # ------------------------------------------------------------------

    op.drop_column(
        "attempts",
        "updated_at",
    )

    op.drop_column(
        "attempts",
        "error_summary",
    )

    op.drop_column(
        "attempts",
        "retryable",
    )

    op.drop_column(
        "case_executions",
        "updated_at",
    )

    # ------------------------------------------------------------------
    # run_events / runs
    # ------------------------------------------------------------------

    op.drop_index(
        "ix_run_events_event_type",
        table_name="run_events",
    )

    op.drop_index(
        "ix_run_events_run_id",
        table_name="run_events",
    )

    op.drop_table(
        "run_events",
    )

    op.drop_column(
        "runs",
        "updated_at",
    )

    op.drop_column(
        "runs",
        "interrupted_at",
    )

    op.drop_column(
        "runs",
        "paused_at",
    )

    op.drop_column(
        "runs",
        "status_reason",
    )

    op.drop_index(
        "ix_runs_benchmark_id",
        table_name="runs",
    )

    op.drop_constraint(
        "fk_runs_benchmark_id_benchmarks",
        "runs",
        type_="foreignkey",
    )

    op.drop_column(
        "runs",
        "benchmark_id",
    )

    # ------------------------------------------------------------------
    # Recreate legacy metric_configs
    # ------------------------------------------------------------------

    op.create_table(
        "metric_configs",
        sa.Column(
            "metric_config_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "selected_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metric_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "judge_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "config_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "metric_config_id",
        ),
    )

    op.create_index(
        "ix_metric_configs_name",
        "metric_configs",
        ["name"],
        unique=False,
    )

    op.create_index(
        "ix_metric_configs_config_hash",
        "metric_configs",
        ["config_hash"],
        unique=False,
    )

    # One legacy MetricConfig is reconstructed per test.  The old shared-object
    # identity cannot be recovered after the upgrade, but the configuration
    # values themselves are preserved.
    op.execute(
        """
        INSERT INTO metric_configs (
            metric_config_id,
            name,
            mode,
            selected_metrics,
            metric_parameters,
            judge_config,
            retrieval_config,
            metadata_json,
            config_hash,
            created_at
        )
        SELECT
            'mc-' || md5(td.test_definition_id),
            td.name || ' metrics',
            CASE
                WHEN td.metric_selection_mode = 'ALL_AVAILABLE'
                    THEN 'all_available'
                ELSE 'explicit'
            END,
            COALESCE(
                (
                    SELECT jsonb_agg(
                        tms.metric_id
                        ORDER BY tms.metric_id
                    )
                    FROM test_metric_selections AS tms
                    WHERE tms.test_definition_id = td.test_definition_id
                      AND tms.enabled = TRUE
                ),
                '[]'::jsonb
            ),
            COALESCE(
                (
                    SELECT jsonb_object_agg(
                        tms.metric_id,
                        tms.parameters
                    )
                    FROM test_metric_selections AS tms
                    WHERE tms.test_definition_id = td.test_definition_id
                      AND tms.enabled = TRUE
                ),
                '{}'::jsonb
            ),
            COALESCE(td.judge_config, '{}'::jsonb),
            COALESCE(td.retrieval_config, '{}'::jsonb),
            '{}'::jsonb,
            md5(
                td.test_definition_id
                || ':'
                || COALESCE(td.definition_hash, '')
            ),
            td.created_at
        FROM test_definitions AS td
        """
    )

    op.add_column(
        "test_definitions",
        sa.Column(
            "metric_config_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE test_definitions
        SET metric_config_id =
            'mc-' || md5(test_definition_id)
        """
    )

    op.create_foreign_key(
        "fk_test_definitions_metric_config_id_metric_configs",
        "test_definitions",
        "metric_configs",
        ["metric_config_id"],
        ["metric_config_id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_test_definitions_metric_config_id",
        "test_definitions",
        ["metric_config_id"],
        unique=False,
    )

    # Backfill a deterministic non-null hash for any test that never became
    # READY under the new schema but is otherwise representable.
    op.execute(
        """
        UPDATE test_definitions
        SET definition_hash = md5(
            test_definition_id
            || ':'
            || COALESCE(target_id, '')
            || ':'
            || COALESCE(benchmark_id, '')
        )
        WHERE definition_hash IS NULL
        """
    )

    op.alter_column(
        "test_definitions",
        "metric_config_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.alter_column(
        "test_definitions",
        "target_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.alter_column(
        "test_definitions",
        "benchmark_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.alter_column(
        "test_definitions",
        "definition_hash",
        existing_type=sa.String(length=64),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Remove new test-owned metric structures
    # ------------------------------------------------------------------

    op.drop_index(
        "ix_test_metric_selections_metric_id",
        table_name="test_metric_selections",
    )

    op.drop_index(
        "ix_test_metric_selections_test_definition_id",
        table_name="test_metric_selections",
    )

    op.drop_table(
        "test_metric_selections",
    )

    op.drop_column(
        "test_definitions",
        "retrieval_config",
    )

    op.drop_column(
        "test_definitions",
        "judge_config",
    )

    op.drop_column(
        "test_definitions",
        "metric_selection_mode",
    )

    op.drop_column(
        "test_definitions",
        "configuration_status",
    )
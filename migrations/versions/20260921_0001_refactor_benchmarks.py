# ruff: noqa: E501
"""Refactor benchmark persistence to canonical benchmark aggregates.

Revision ID: 20260921_0001
Revises: stage15_domain_resources
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260921_0001"
down_revision: str | None = "stage15_domain_resources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate benchmark persistence to the canonical benchmark model."""

    # ------------------------------------------------------------------
    # benchmarks
    # ------------------------------------------------------------------

    # Add fields required by the new BenchmarkManifest / BenchmarkRecord.
    #
    # DOCUMENTS is used temporarily as a migration default so existing rows
    # can satisfy the new NOT NULL constraint.
    op.add_column(
        "benchmarks",
        sa.Column(
            "corpus_mode",
            sa.String(length=32),
            nullable=False,
            server_default="DOCUMENTS",
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "corpus_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_index(
        "ix_benchmarks_corpus_mode",
        "benchmarks",
        ["corpus_mode"],
        unique=False,
    )

    op.create_index(
        "ix_benchmarks_content_hash",
        "benchmarks",
        ["content_hash"],
        unique=False,
    )

    op.create_index(
        "ix_benchmarks_corpus_id",
        "benchmarks",
        ["corpus_id"],
        unique=False,
    )

    # Existing Stage 15 fields no longer belong to the canonical benchmark
    # persistence model.
    op.drop_column("benchmarks", "manifest_path")
    op.drop_column("benchmarks", "manifest_hash")
    op.drop_column("benchmarks", "provenance")
    op.drop_column("benchmarks", "case_count")
    op.drop_column("benchmarks", "document_count")

    # corpus_mode should have an application-level default, not a permanent
    # database server default.
    op.alter_column(
        "benchmarks",
        "corpus_mode",
        server_default=None,
    )

    # ------------------------------------------------------------------
    # benchmark_cases
    # ------------------------------------------------------------------

    # Add the new ownership column first while nullable so old rows can be
    # migrated safely.
    op.add_column(
        "benchmark_cases",
        sa.Column(
            "benchmark_id",
            sa.String(length=128),
            nullable=True,
        ),
    )

    # Carry forward the old dataset_id when it already corresponds to an
    # existing benchmark identity.
    op.execute(
        """
        UPDATE benchmark_cases
        SET benchmark_id = dataset_id
        WHERE dataset_id IS NOT NULL
          AND dataset_id IN (
              SELECT benchmark_id
              FROM benchmarks
          )
        """
    )

    # If legacy dataset IDs exist without BenchmarkRecord rows, create minimal
    # benchmark identities for them so benchmark truth is not lost.
    op.execute(
        """
        INSERT INTO benchmarks (
            benchmark_id,
            name,
            version,
            schema_version,
            corpus_mode,
            tags,
            metadata_json,
            created_at
        )
        SELECT DISTINCT
            bc.dataset_id,
            bc.dataset_id,
            '1',
            '1.0',
            'DOCUMENTS',
            '[]'::jsonb,
            jsonb_build_object(
                'migrated_from_dataset_id',
                true
            ),
            now()
        FROM benchmark_cases bc
        WHERE bc.dataset_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM benchmarks b
              WHERE b.benchmark_id = bc.dataset_id
          )
        """
    )

    # Populate benchmark_id for those newly created legacy benchmark rows.
    op.execute(
        """
        UPDATE benchmark_cases
        SET benchmark_id = dataset_id
        WHERE benchmark_id IS NULL
          AND dataset_id IS NOT NULL
        """
    )

    # Cases with no historical dataset identity still need a valid benchmark.
    # Create one shared legacy benchmark only when such rows exist.
    op.execute(
        """
        INSERT INTO benchmarks (
            benchmark_id,
            name,
            version,
            schema_version,
            corpus_mode,
            tags,
            metadata_json,
            created_at
        )
        SELECT
            'legacy-unassigned-benchmark',
            'Legacy Unassigned Benchmark',
            '1',
            '1.0',
            'DOCUMENTS',
            '[]'::jsonb,
            jsonb_build_object(
                'migration_placeholder',
                true
            ),
            now()
        WHERE EXISTS (
            SELECT 1
            FROM benchmark_cases
            WHERE benchmark_id IS NULL
        )
        AND NOT EXISTS (
            SELECT 1
            FROM benchmarks
            WHERE benchmark_id = 'legacy-unassigned-benchmark'
        )
        """
    )

    op.execute(
        """
        UPDATE benchmark_cases
        SET benchmark_id = 'legacy-unassigned-benchmark'
        WHERE benchmark_id IS NULL
        """
    )

    # benchmark_id can now become the required ownership relationship.
    op.alter_column(
        "benchmark_cases",
        "benchmark_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.create_foreign_key(
        "fk_benchmark_cases_benchmark_id_benchmarks",
        "benchmark_cases",
        "benchmarks",
        ["benchmark_id"],
        ["benchmark_id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_benchmark_cases_benchmark_id",
        "benchmark_cases",
        ["benchmark_id"],
        unique=False,
    )

    # Remove the obsolete dataset abstraction.
    op.drop_column(
        "benchmark_cases",
        "dataset_id",
    )

    # ------------------------------------------------------------------
    # benchmark_documents
    # ------------------------------------------------------------------

    op.create_table(
        "benchmark_documents",
        sa.Column(
            "document_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "benchmark_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "filename",
            sa.String(length=1024),
            nullable=True,
        ),
        sa.Column(
            "mime_type",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "sha256",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "size_bytes",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "artifact_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
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
            ["benchmark_id"],
            ["benchmarks.benchmark_id"],
            name="fk_benchmark_documents_benchmark_id_benchmarks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.artifact_id"],
            name="fk_benchmark_documents_artifact_id_artifacts",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )

    op.create_index(
        "ix_benchmark_documents_benchmark_id",
        "benchmark_documents",
        ["benchmark_id"],
        unique=False,
    )

    op.create_index(
        "ix_benchmark_documents_sha256",
        "benchmark_documents",
        ["sha256"],
        unique=False,
    )

    op.create_index(
        "ix_benchmark_documents_artifact_id",
        "benchmark_documents",
        ["artifact_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # benchmark_chunks
    # ------------------------------------------------------------------

    op.create_table(
        "benchmark_chunks",
        sa.Column(
            "chunk_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "benchmark_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "location",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
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
            ["benchmark_id"],
            ["benchmarks.benchmark_id"],
            name="fk_benchmark_chunks_benchmark_id_benchmarks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
    )

    op.create_index(
        "ix_benchmark_chunks_benchmark_id",
        "benchmark_chunks",
        ["benchmark_id"],
        unique=False,
    )

    op.create_index(
        "ix_benchmark_chunks_document_id",
        "benchmark_chunks",
        ["document_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Existing Stage 4 inconsistency
    # ------------------------------------------------------------------

    # AggregateMetricResultRecord / repository now use aggregate.aggregation,
    # but the original Stage 4 migration never created this column.
    op.add_column(
        "aggregate_metric_results",
        sa.Column(
            "aggregation",
            sa.String(length=64),
            nullable=False,
            server_default="mean",
        ),
    )

    op.alter_column(
        "aggregate_metric_results",
        "aggregation",
        server_default=None,
    )


def downgrade() -> None:
    """Restore the pre-canonical benchmark schema."""

    # ------------------------------------------------------------------
    # Aggregate metric compatibility
    # ------------------------------------------------------------------

    op.drop_column(
        "aggregate_metric_results",
        "aggregation",
    )

    # ------------------------------------------------------------------
    # Benchmark chunks/documents
    # ------------------------------------------------------------------

    op.drop_index(
        "ix_benchmark_chunks_document_id",
        table_name="benchmark_chunks",
    )

    op.drop_index(
        "ix_benchmark_chunks_benchmark_id",
        table_name="benchmark_chunks",
    )

    op.drop_table("benchmark_chunks")

    op.drop_index(
        "ix_benchmark_documents_artifact_id",
        table_name="benchmark_documents",
    )

    op.drop_index(
        "ix_benchmark_documents_sha256",
        table_name="benchmark_documents",
    )

    op.drop_index(
        "ix_benchmark_documents_benchmark_id",
        table_name="benchmark_documents",
    )

    op.drop_table("benchmark_documents")

    # ------------------------------------------------------------------
    # benchmark_cases
    # ------------------------------------------------------------------

    op.add_column(
        "benchmark_cases",
        sa.Column(
            "dataset_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE benchmark_cases
        SET dataset_id = benchmark_id
        """
    )

    op.drop_index(
        "ix_benchmark_cases_benchmark_id",
        table_name="benchmark_cases",
    )

    op.drop_constraint(
        "fk_benchmark_cases_benchmark_id_benchmarks",
        "benchmark_cases",
        type_="foreignkey",
    )

    op.drop_column(
        "benchmark_cases",
        "benchmark_id",
    )

    # ------------------------------------------------------------------
    # benchmarks
    # ------------------------------------------------------------------

    op.add_column(
        "benchmarks",
        sa.Column(
            "manifest_path",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "manifest_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "case_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "benchmarks",
        sa.Column(
            "document_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.drop_index(
        "ix_benchmarks_corpus_id",
        table_name="benchmarks",
    )

    op.drop_index(
        "ix_benchmarks_content_hash",
        table_name="benchmarks",
    )

    op.drop_index(
        "ix_benchmarks_corpus_mode",
        table_name="benchmarks",
    )

    op.drop_column(
        "benchmarks",
        "tags",
    )

    op.drop_column(
        "benchmarks",
        "corpus_id",
    )

    op.drop_column(
        "benchmarks",
        "content_hash",
    )

    op.drop_column(
        "benchmarks",
        "corpus_mode",
    )
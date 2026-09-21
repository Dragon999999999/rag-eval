# ruff: noqa: E501
"""Refactor target persistence for managed adapter configuration.

Revision ID: 20260921_0002
Revises: 20260921_0001
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260921_0002"
down_revision: str | None = "20260921_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate target persistence to evaluator-managed target lifecycle."""

    # ------------------------------------------------------------------
    # targets
    # ------------------------------------------------------------------

    # Preserve the old remote-advertised version / implementation fields in
    # metadata before removing them from evaluator-owned target identity.
    op.execute(
        """
        UPDATE targets
        SET metadata_json =
            COALESCE(metadata_json, '{}'::jsonb)
            ||
            jsonb_build_object(
                'legacy_remote_identity',
                jsonb_strip_nulls(
                    jsonb_build_object(
                        'version', version,
                        'implementation', implementation
                    )
                )
            )
        WHERE version IS NOT NULL
           OR implementation IS NOT NULL
        """
    )

    op.add_column(
        "targets",
        sa.Column(
            "adapter_type",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "configuration_status",
            sa.String(length=32),
            nullable=False,
            server_default="empty",
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "current_config_version",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Existing targets predate managed target configuration, so they correctly
    # begin in EMPTY state with no current config version.
    op.alter_column(
        "targets",
        "configuration_status",
        server_default=None,
    )

    op.alter_column(
        "targets",
        "enabled",
        server_default=None,
    )

    # version / implementation are remote-advertised TargetInfo fields and no
    # longer belong to evaluator-owned TargetRecord.
    op.drop_column(
        "targets",
        "version",
    )

    op.drop_column(
        "targets",
        "implementation",
    )

    # ------------------------------------------------------------------
    # target_config_versions
    # ------------------------------------------------------------------

    op.create_table(
        "target_config_versions",
        sa.Column(
            "config_version_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "source_artifact_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "declared_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "effective_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
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
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.target_id"],
            name="fk_target_config_versions_target_id_targets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["artifacts.artifact_id"],
            name="fk_target_config_versions_source_artifact_id_artifacts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "config_version_id",
        ),
        sa.UniqueConstraint(
            "target_id",
            "version",
            name="uq_target_config_versions_target_version",
        ),
    )

    op.create_index(
        "ix_target_config_versions_target_id",
        "target_config_versions",
        ["target_id"],
        unique=False,
    )

    op.create_index(
        "ix_target_config_versions_config_hash",
        "target_config_versions",
        ["config_hash"],
        unique=False,
    )

    op.create_index(
        "ix_target_config_versions_source_artifact_id",
        "target_config_versions",
        ["source_artifact_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # target_secrets
    # ------------------------------------------------------------------

    # Only encrypted bytes are stored here. The encryption key is external
    # application configuration and must never be persisted in this table.
    op.create_table(
        "target_secrets",
        sa.Column(
            "secret_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "encrypted_value",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "key_version",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.target_id"],
            name="fk_target_secrets_target_id_targets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "secret_id",
        ),
        sa.UniqueConstraint(
            "target_id",
            "name",
            name="uq_target_secrets_target_name",
        ),
    )

    op.create_index(
        "ix_target_secrets_target_id",
        "target_secrets",
        ["target_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # target_connections
    # ------------------------------------------------------------------

    # Evaluator-observed connectivity is deliberately separate from the
    # target-advertised HealthStatus payload.
    op.create_table(
        "target_connections",
        sa.Column(
            "target_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_successful_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "health_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "error_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            ["target_id"],
            ["targets.target_id"],
            name="fk_target_connections_target_id_targets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "target_id",
        ),
    )

    # Existing targets should have an explicit NOT_TESTED state rather than
    # requiring callers to interpret an absent connection row.
    op.execute(
        """
        INSERT INTO target_connections (
            target_id,
            status,
            created_at,
            updated_at
        )
        SELECT
            target_id,
            'not_tested',
            now(),
            now()
        FROM targets
        """
    )

    # ------------------------------------------------------------------
    # target_capabilities
    # ------------------------------------------------------------------

    # Capability payload remains JSONB, but now records when it was most
    # recently discovered.
    op.add_column(
        "target_capabilities",
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Existing capability rows represent previously discovered capabilities,
    # so their creation timestamp is the best migration-time approximation.
    op.execute(
        """
        UPDATE target_capabilities
        SET checked_at = created_at
        WHERE checked_at IS NULL
        """
    )

    op.alter_column(
        "target_capabilities",
        "checked_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    """Restore the previous target persistence model."""

    # ------------------------------------------------------------------
    # target_capabilities
    # ------------------------------------------------------------------

    op.drop_column(
        "target_capabilities",
        "checked_at",
    )

    # ------------------------------------------------------------------
    # target_connections
    # ------------------------------------------------------------------

    op.drop_table(
        "target_connections",
    )

    # ------------------------------------------------------------------
    # target_secrets
    # ------------------------------------------------------------------

    op.drop_index(
        "ix_target_secrets_target_id",
        table_name="target_secrets",
    )

    op.drop_table(
        "target_secrets",
    )

    # ------------------------------------------------------------------
    # target_config_versions
    # ------------------------------------------------------------------

    op.drop_index(
        "ix_target_config_versions_source_artifact_id",
        table_name="target_config_versions",
    )

    op.drop_index(
        "ix_target_config_versions_config_hash",
        table_name="target_config_versions",
    )

    op.drop_index(
        "ix_target_config_versions_target_id",
        table_name="target_config_versions",
    )

    op.drop_table(
        "target_config_versions",
    )

    # ------------------------------------------------------------------
    # targets
    # ------------------------------------------------------------------

    op.add_column(
        "targets",
        sa.Column(
            "version",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "targets",
        sa.Column(
            "implementation",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # Recover the legacy values when this migration itself preserved them.
    op.execute(
        """
        UPDATE targets
        SET
            version = metadata_json
                -> 'legacy_remote_identity'
                ->> 'version',
            implementation = metadata_json
                -> 'legacy_remote_identity'
                ->> 'implementation'
        WHERE metadata_json ? 'legacy_remote_identity'
        """
    )

    # Remove only the migration-owned metadata key while preserving all other
    # target metadata.
    op.execute(
        """
        UPDATE targets
        SET metadata_json =
            metadata_json - 'legacy_remote_identity'
        WHERE metadata_json ? 'legacy_remote_identity'
        """
    )

    op.drop_column(
        "targets",
        "updated_at",
    )

    op.drop_column(
        "targets",
        "enabled",
    )

    op.drop_column(
        "targets",
        "current_config_version",
    )

    op.drop_column(
        "targets",
        "configuration_status",
    )

    op.drop_column(
        "targets",
        "adapter_type",
    )
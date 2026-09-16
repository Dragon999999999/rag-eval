"""Add Stage 15 domain resources: benchmarks, metric_configs, test_definitions.

Revision ID: stage15_domain_resources
Revises: 
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'stage15_domain_resources'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Stage 15 domain resource tables."""
    
    # Create benchmarks table
    op.create_table(
        'benchmarks',
        sa.Column('benchmark_id', sa.String(128), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('version', sa.String(64), nullable=False),
        sa.Column('manifest_path', sa.Text, nullable=True),
        sa.Column('manifest_hash', sa.String(64), nullable=True, index=True),
        sa.Column('schema_version', sa.String(64), nullable=False, default='1.0'),
        sa.Column('source', sa.Text, nullable=True),
        sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('case_count', sa.Integer, nullable=True),
        sa.Column('document_count', sa.Integer, nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('benchmark_id')
    )
    
    # Create metric_configs table
    op.create_table(
        'metric_configs',
        sa.Column('metric_config_id', sa.String(128), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('mode', sa.String(64), nullable=False),
        sa.Column('selected_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column('metric_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('judge_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('retrieval_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('config_hash', sa.String(64), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('metric_config_id')
    )
    
    # Create test_definitions table
    op.create_table(
        'test_definitions',
        sa.Column('test_definition_id', sa.String(128), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('target_id', sa.String(128), nullable=False, index=True),
        sa.Column('benchmark_id', sa.String(128), nullable=False, index=True),
        sa.Column('metric_config_id', sa.String(128), nullable=False, index=True),
        sa.Column('execution_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('seed', sa.Integer, nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=list),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, default=dict),
        sa.Column('definition_hash', sa.String(64), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['targets.target_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['benchmark_id'], ['benchmarks.benchmark_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['metric_config_id'], ['metric_configs.metric_config_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('test_definition_id')
    )
    
    # Add test_definition_id to runs table
    op.add_column(
        'runs',
        sa.Column('test_definition_id', sa.String(128), nullable=True)
    )
    
    # Create index for runs.test_definition_id
    op.create_index(
        op.f('ix_runs_test_definition_id'),
        'runs',
        ['test_definition_id'],
        unique=False
    )
    
    # Create foreign key for runs.test_definition_id
    op.create_foreign_key(
        op.f('fk_runs_test_definition_id_test_definitions'),
        'runs',
        'test_definitions',
        ['test_definition_id'],
        ['test_definition_id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove Stage 15 domain resource tables."""
    # Drop foreign key from runs
    op.drop_constraint(
        op.f('fk_runs_test_definition_id_test_definitions'),
        'runs',
        type_='foreignkey'
    )
    
    # Drop index from runs
    op.drop_index(
        op.f('ix_runs_test_definition_id'),
        table_name='runs'
    )
    
    # Drop test_definition_id column from runs
    op.drop_column('runs', 'test_definition_id')
    
    # Drop test_definitions table
    op.drop_table('test_definitions')
    
    # Drop metric_configs table
    op.drop_table('metric_configs')
    
    # Drop benchmarks table
    op.drop_table('benchmarks')

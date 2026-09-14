# ruff: noqa: E501, I001
"""Create the Stage 4 PostgreSQL persistence schema.

Revision ID: 20260914_0001
Revises:
Create Date: 2026-09-14
"""

from alembic import op


revision = "20260914_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable relational records and selective JSONB payload storage."""
    statements = [
        "CREATE TABLE run_configs (config_hash varchar(64) PRIMARY KEY, canonical_config jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE targets (target_id varchar(128) PRIMARY KEY, name varchar(255) NOT NULL, version varchar(255), implementation varchar(255), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE target_capabilities (target_id varchar(128) PRIMARY KEY REFERENCES targets(target_id) ON DELETE CASCADE, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE runs (run_id varchar(128) PRIMARY KEY, name varchar(255) NOT NULL, status varchar(64) NOT NULL, config_hash varchar(64) NOT NULL REFERENCES run_configs(config_hash) ON DELETE RESTRICT, target_id varchar(128) REFERENCES targets(target_id) ON DELETE SET NULL, started_at timestamptz, finished_at timestamptz, seed integer, rag_eval_version varchar(64), tags jsonb NOT NULL DEFAULT '[]'::jsonb, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE corpora (corpus_id varchar(128) PRIMARY KEY, target_id varchar(128) REFERENCES targets(target_id) ON DELETE SET NULL, mode varchar(32) NOT NULL, status varchar(64) NOT NULL, content_hash varchar(64), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE artifacts (artifact_id varchar(128) PRIMARY KEY, artifact_type varchar(64) NOT NULL, uri text NOT NULL, sha256 varchar(64), size_bytes integer, content_type varchar(255), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE documents (document_id varchar(128) PRIMARY KEY, corpus_id varchar(128) NOT NULL REFERENCES corpora(corpus_id) ON DELETE CASCADE, filename varchar(1024), mime_type varchar(255), sha256 varchar(64), size_bytes integer, artifact_id varchar(128) REFERENCES artifacts(artifact_id), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE benchmark_cases (case_id varchar(128) PRIMARY KEY, dataset_id varchar(255), query text NOT NULL, history jsonb NOT NULL DEFAULT '[]'::jsonb, reference_answer text, gold_evidence jsonb NOT NULL DEFAULT '[]'::jsonb, answerability varchar(32), tags jsonb NOT NULL DEFAULT '[]'::jsonb, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE case_executions (case_execution_id varchar(128) PRIMARY KEY, run_id varchar(128) NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE, case_id varchar(128) NOT NULL REFERENCES benchmark_cases(case_id) ON DELETE RESTRICT, status varchar(64) NOT NULL, started_at timestamptz, finished_at timestamptz, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_case_execution_run_case UNIQUE(run_id, case_id))",
        "CREATE TABLE attempts (attempt_id varchar(128) PRIMARY KEY, case_execution_id varchar(128) NOT NULL REFERENCES case_executions(case_execution_id) ON DELETE CASCADE, attempt_number integer NOT NULL, request_id varchar(128) NOT NULL UNIQUE, idempotency_key varchar(255), canonical_request_hash varchar(64), status varchar(64) NOT NULL, started_at timestamptz, finished_at timestamptz, raw_request_artifact_id varchar(128) REFERENCES artifacts(artifact_id), raw_response_artifact_id varchar(128) REFERENCES artifacts(artifact_id), metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_attempt_case_number UNIQUE(case_execution_id, attempt_number))",
        "CREATE TABLE stage_executions (stage_execution_id varchar(128) PRIMARY KEY, attempt_id varchar(128) NOT NULL REFERENCES attempts(attempt_id) ON DELETE CASCADE, stage_name varchar(255) NOT NULL, status varchar(64) NOT NULL, started_at timestamptz, finished_at timestamptz, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE target_observations (observation_id varchar(128) PRIMARY KEY, request_id varchar(128) NOT NULL UNIQUE, case_execution_id varchar(128) NOT NULL REFERENCES case_executions(case_execution_id) ON DELETE CASCADE, attempt_id varchar(128) NOT NULL UNIQUE REFERENCES attempts(attempt_id) ON DELETE CASCADE, normalization_version varchar(64) NOT NULL, payload jsonb NOT NULL, payload_hash varchar(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE metric_results (metric_result_id varchar(128) PRIMARY KEY, run_id varchar(128) NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE, case_execution_id varchar(128) REFERENCES case_executions(case_execution_id) ON DELETE CASCADE, case_id varchar(128) REFERENCES benchmark_cases(case_id), metric_id varchar(255) NOT NULL, metric_version varchar(64) NOT NULL, value jsonb, status varchar(64) NOT NULL, reason text, details jsonb NOT NULL DEFAULT '{}'::jsonb, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE aggregate_metric_results (aggregate_metric_result_id varchar(128) PRIMARY KEY, run_id varchar(128) NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE, metric_id varchar(255) NOT NULL, metric_version varchar(64) NOT NULL, value jsonb, status varchar(64) NOT NULL, reason text, details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE TABLE errors (error_id varchar(128) PRIMARY KEY, run_id varchar(128) REFERENCES runs(run_id) ON DELETE CASCADE, case_execution_id varchar(128) REFERENCES case_executions(case_execution_id) ON DELETE CASCADE, attempt_id varchar(128) REFERENCES attempts(attempt_id) ON DELETE CASCADE, category varchar(64) NOT NULL, code varchar(255) NOT NULL, message text NOT NULL, stage varchar(255), retryable boolean NOT NULL DEFAULT false, retry_after_ms integer, http_status integer, provider jsonb NOT NULL DEFAULT '{}'::jsonb, raw_artifact_id varchar(128) REFERENCES artifacts(artifact_id), details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now())",
        "CREATE INDEX ix_runs_status ON runs(status)",
        "CREATE INDEX ix_case_executions_status ON case_executions(status)",
        "CREATE INDEX ix_attempts_case_execution_id ON attempts(case_execution_id)",
        "CREATE INDEX ix_attempts_status ON attempts(status)",
        "CREATE INDEX ix_metric_results_run_id ON metric_results(run_id)",
        "CREATE INDEX ix_errors_attempt_id ON errors(attempt_id)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    """Drop all Stage 4 records in foreign-key dependency order."""
    for table in [
        "errors",
        "aggregate_metric_results",
        "metric_results",
        "target_observations",
        "stage_executions",
        "attempts",
        "case_executions",
        "benchmark_cases",
        "documents",
        "artifacts",
        "corpora",
        "runs",
        "target_capabilities",
        "targets",
        "run_configs",
    ]:
        op.execute(f"DROP TABLE {table}")

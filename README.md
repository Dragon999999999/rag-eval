# rag-eval

`rag-eval` is a modular evaluation framework for RAG and LLM systems. This
initial stage provides the runnable Python application, environment-driven
configuration, PostgreSQL migration foundation, and local PostgreSQL/MinIO
infrastructure. Evaluation features are not implemented yet.

## Local setup

Install the application and development dependencies:

```bash
uv sync
```

Optionally copy `.env.example` to `.env` to customize the local service
credentials and ports. The checked-in defaults work for local development.

Start PostgreSQL and MinIO; Compose creates the configured artifact bucket
automatically:

```bash
docker compose up -d
```

Verify the installed CLI:

```bash
uv run rag-eval --help
uv run rag-eval version
```

Validate a static experiment definition and inspect its non-executing plan:

```bash
uv run rag-eval validate examples/basic.yaml
uv run rag-eval plan examples/basic.yaml
```

The YAML configuration supports deterministic matrix expansion and stable
configuration hashes. Secret-bearing values are referenced by environment
variable name and are not included in plans or configuration identities.

Run the normal unit test suite (it does not require external services):

```bash
uv run pytest
```

PostgreSQL is exposed on `localhost:5433`, MinIO's S3 API on
`http://localhost:9002`, and its console on `http://localhost:9003` by
default. The artifact bucket is `rag-eval-artifacts` unless
`RAG_EVAL_S3_BUCKET` is set.

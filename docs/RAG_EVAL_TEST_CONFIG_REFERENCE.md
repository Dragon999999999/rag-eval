# `rag-eval` Test / Experiment Configuration Reference

This document describes the configuration surface evidenced by the current `rag-eval`
design and code snippets. YAML is the intended human-authored configuration format for
commands such as:

```bash
uv run rag-eval validate CONFIG
uv run rag-eval plan CONFIG
uv run rag-eval corpus prepare CONFIG
uv run rag-eval run CONFIG
```

The canonical experiment configuration is designed around these top-level sections:

```yaml
version:
run:
dataset:
target:
execution:
metrics:
storage:
persistence:
output:
matrix:
```

Not every section must necessarily be present in every checkout or deployment. The
authoritative validator is the Pydantic configuration model in `rag_eval.config`
(`ExperimentConfig` and its nested models). Where the core deliberately accepts a free-form
dictionary, the keys are target- or deployment-specific rather than globally enumerated.

---

## 1. `version`

Configuration schema/protocol version.

```yaml
version: "1"
```

Use the version expected by the current evaluator implementation. It participates in
reproducible configuration identity.

---

## 2. `run`

Static metadata and reproducibility settings for the evaluation run.

```yaml
run:
  name: "baseline-rag-evaluation"
  seed: 42
  resume: true
  tags: ["baseline", "local"]
  metadata:
    purpose: "Compare retrieval settings"
```

### Fields

| Field | Type | Purpose |
|---|---|---|
| `name` | string | Human-readable run/experiment name. |
| `seed` | integer | Reproducibility seed. |
| `resume` | boolean | Whether the run should use resume/recovery semantics where supported. |
| `tags` | list[string] | User-defined labels for grouping/searching runs. |
| `metadata` | object | Arbitrary non-secret descriptive metadata. |

Runtime lifecycle state such as `status`, `started_at`, `finished_at`, retry history, and
case progress belongs in persisted run state, not in this static file.

---

## 3. `dataset`

Identifies the benchmark dataset.

Minimal native configuration:

```yaml
dataset:
  manifest: "./examples/benchmark-manifest.yaml"
```

### Supported concepts

| Field / concept | Type | Purpose |
|---|---|---|
| `manifest` | path/string | Path to the native benchmark manifest. |
| dataset identifier | string, optional | Stable dataset/benchmark identity where the concrete model exposes it. |
| dataset version | string, optional | Version of the benchmark where applicable. |

The native benchmark manifest may define:

- benchmark identity/name/version;
- source documents;
- document SHA-256 hashes;
- canonical chunks;
- JSON or JSONL cases;
- case count and provenance.

JSONL case iteration is intended to remain lazy/streaming for large benchmarks.

---

## 4. `target`

Defines the system being evaluated.

```yaml
target:
  adapter: "http"
  base_url: "http://localhost:8000"

  corpus:
    mode: "DOCUMENTS"
    parameters: {}

  parameters:
    top_k: 10
```

### 4.1 `adapter`

Supported adapter families are:

```yaml
adapter: "http"
```

or:

```yaml
adapter: "python"
```

`http` communicates with a Target Protocol v1 server. `python` loads a local target by an
explicit import path.

### 4.2 HTTP target

The HTTP adapter uses a base URL such as:

```yaml
base_url: "http://localhost:8000"
```

The adapter appends Target Protocol v1 routes under `/eval/v1/...`.

The current HTTP adapter supports, subject to target capabilities:

- health;
- capabilities;
- target config schema;
- create/get/delete corpus;
- document upload;
- chunk upload;
- operation polling;
- retrieve;
- query;
- query streaming;
- request recovery.

### 4.3 Python target

A Python target is identified by an explicit import target conceptually like:

```yaml
target:
  adapter: "python"
  import: "my_project.eval_target:MyTarget"
```

The exact property name for the import path should be checked against the current
`TargetConfig` model in the checkout. Arbitrary Python expressions are intentionally not
supported.

### 4.4 Authentication

HTTP authentication is designed to support:

- no authentication;
- bearer token;
- custom API-key header.

Secrets should be resolved from environment-backed references. Do **not** put resolved
tokens, passwords, or API keys into the canonical YAML.

Conceptually:

```yaml
authentication:
  type: "bearer"
  token_env: "RAG_EVAL_TARGET_TOKEN"
```

or:

```yaml
authentication:
  type: "api_key"
  key_env: "RAG_EVAL_TARGET_API_KEY"
  header: "X-API-Key"
```

The exact nested field names are implementation-specific; confirm them against the current
Pydantic config model. Secret values must be excluded from canonical hashes, exported
configs, logs, and manifests.

---

## 5. `target.corpus`

Controls how benchmark knowledge reaches the target.

### `DOCUMENTS`

```yaml
target:
  corpus:
    mode: "DOCUMENTS"
    parameters: {}
```

`rag-eval` uploads benchmark source documents and waits for ingestion to reach a terminal
successful state. The target must advertise document-ingestion capability.

### `CHUNKS`

```yaml
target:
  corpus:
    mode: "CHUNKS"
    parameters: {}
```

`rag-eval` uploads canonical benchmark chunks. The target must advertise chunk-ingestion
capability. The evaluator is expected to respect target-advertised batch limits.

### `EXTERNAL`

```yaml
target:
  corpus:
    mode: "EXTERNAL"
    corpus_id: "already-managed-corpus"
    parameters: {}
```

Nothing is uploaded. The target corpus already exists and is managed externally.
`corpus_id` is required for this mode.

### Corpus fields

| Field | Type | Purpose |
|---|---|---|
| `mode` | `DOCUMENTS` / `CHUNKS` / `EXTERNAL` | Select corpus preparation strategy. |
| `corpus_id` | string or null | Existing target corpus identifier; required for `EXTERNAL`. |
| `parameters` | object | Arbitrary target corpus/ingestion parameters. |

Corpus `parameters` are intentionally open-ended.

---

## 6. `target.parameters`

Free-form target/RAG configuration. This is the main place for parameters that affect the
evaluated RAG implementation but are not universal evaluator concepts.

Example:

```yaml
target:
  parameters:
    embedding_model: "bge-m3"
    chunk_size: 512
    chunk_overlap: 64
    top_k: 10
    reranker: "none"
    generation_model: "qwen-3.5-397b"
    prompt_version: "v1"
```

These names are **examples**, not globally mandated keys. The selected target defines their
meaning. Other valid target-specific parameters may be added freely if the target accepts
them.

Typical categories include:

- embedding model/version;
- chunking method;
- chunk size;
- chunk overlap;
- retrieval `top_k`;
- lexical/vector/hybrid retrieval switches;
- reranker and reranker parameters;
- generation/model identifier;
- temperature or other model controls;
- prompt/template version;
- context-window limits;
- target-specific feature flags.

Use the target's optional `/eval/v1/config-schema` endpoint when available to discover its
own parameter schema.

---

## 7. `execution`

Evaluator-side execution controls.

```yaml
execution:
  concurrency: 4
  connect_timeout: 10.0
  request_timeout: 60.0
  total_timeout: 120.0
```

### Core fields

| Field | Type | Meaning |
|---|---|---|
| `concurrency` | integer >= 1 | Maximum bounded case concurrency. |
| `connect_timeout` | positive number | Maximum connection-establishment time in seconds. |
| `request_timeout` | positive number | Request/read/write timeout in seconds. |
| `total_timeout` | positive number | Overall/pool/total timeout as defined by the adapter/executor. |

The execution engine explicitly reads these four fields.

### Execution mode

The architecture supports query and retrieval-only execution internally. If the current
config model exposes an execution-mode field, use the canonical enum/value required by
that checkout. The engine should not conceptually force every future benchmark through
generation.

### Streaming

Streaming may be used when configured and supported by the target. When enabled, the
execution layer can preserve stream events, partial output, and first-token timing.
The exact config key is implementation-specific unless exposed by the current Pydantic
model.

### Continue-on-case-failure

The architecture favors recording an individual failed case and continuing other cases.
If the current config exposes a failure-policy option, this belongs under execution rather
than target settings.

---

## 8. `execution.retry`

The Stage-3 configuration contract includes retry configuration with at least these
concepts:

```yaml
execution:
  retry:
    max_attempts: 3
    strategy: "exponential"
    initial_delay: 1.0
    maximum_delay: 30.0
    retryable_http_statuses: [429, 500, 502, 503, 504]
    retryable_categories:
      - RATE_LIMIT
      - TIMEOUT
      - CONNECTION
```

### Retry concepts

| Concept | Meaning |
|---|---|
| maximum attempts | Hard bound on attempts for one logical case request. |
| strategy | Backoff policy, e.g. fixed/exponential if supported. |
| initial delay | First backoff duration. |
| maximum delay | Cap on backoff duration. |
| retryable HTTP statuses | Status codes eligible for retry. |
| retryable error categories | Normalized error categories eligible for retry. |

The resilient execution layer preserves attempts append-only, reuses stable idempotency
identity for retries, and should not regenerate a durably captured target result.

**Important:** verify the exact field names against the current `RetryConfig` Pydantic
model before uncommenting them in production YAML. The architecture clearly requires
these concepts, but the exact spelling is an implementation detail.

---

## 9. Circuit breaker / recovery controls

The resilience design includes target-level circuit breaking and stale-run recovery:

- states: `CLOSED`, `OPEN`, `HALF_OPEN`;
- repeated transient failures may open the breaker;
- cooldown before probing/recovery;
- request recovery when supported;
- idempotent replay as a fallback;
- stale `RUNNING` attempt handling;
- partial-stream preservation.

If your current configuration model exposes thresholds, cooldowns, or staleness settings,
document them under `execution` and use the names from the actual Pydantic model. Do not
invent keys solely from the architecture document.

---

## 10. `metrics`

Controls metric selection.

```yaml
metrics:
  mode: "all_available"
  selected_metrics: []
```

### `mode`

Supported selection modes in the metric engine are:

- `all_available`
- `explicit`

### `selected_metrics`

Used when:

```yaml
mode: "explicit"
```

Example:

```yaml
metrics:
  mode: "explicit"
  selected_metrics:
    - "answer.exact_match"
    - "answer.token_f1"
    - "retrieval.recall_at_k"
    - "retrieval.mrr"
    - "citation.resolution"
    - "performance.total_latency_ms"
    - "usage.total_tokens"
```

### Metric version overrides

The scoring engine also supports a mapping of metric ID to implementation version:

```yaml
metric_versions:
  answer.token_f1: "1"
```

Whether this appears directly in `metrics` depends on the current config integration.

### Persisting unavailable/failed results

The metric execution engine supports:

```text
persist_unavailable
persist_failed
```

These decide whether `UNAVAILABLE_*` and `FAILED` metric results are persisted rather
than skipped. If exposed by the experiment config, they belong under metrics/scoring.

### Judge configuration

The configuration design reserves optional judge configuration for future semantic metrics:

```yaml
metrics:
  judge: {}
```

Judge execution was intentionally not required for the initial deterministic catalog.

---

## 11. Initial deterministic metric catalog

The current metric catalog includes families such as:

### Answer metrics

Examples include:

- `answer.exact_match`
- `answer.normalized_exact_match`
- `answer.token_precision`
- `answer.token_recall`
- `answer.token_f1`

### Retrieval metrics

- `retrieval.hit_at_k`
- `retrieval.precision_at_k`
- `retrieval.recall_at_k`
- `retrieval.mrr`
- `retrieval.map_at_k`
- `retrieval.ndcg_at_k`
- `retrieval.r_precision`

### Citation metrics

- `citation.resolution`
- `citation.attribution_rate`
- `citation.broken`

### Performance metrics

- `performance.total_latency_ms`
- `performance.retrieval_latency_ms`
- `performance.generation_latency_ms`
- `performance.tokens_per_second`

### Usage / cost metrics

- `usage.total_tokens`
- `usage.input_tokens`
- `usage.output_tokens`
- cost-oriented metrics where cost information is supplied by the target.

A selected metric may still become unavailable for an individual case if its required
inputs are absent. For example, retrieval metrics require retrieval output and gold
evidence.

---

## 12. `storage`

The Stage-3 design provides storage configuration for PostgreSQL and artifact storage,
preferably using environment references.

Conceptually:

```yaml
storage:
  database:
    url_env: "RAG_EVAL_DATABASE_URL"

  artifacts:
    endpoint_env: "RAG_EVAL_S3_ENDPOINT"
    bucket: "rag-eval"
```

Artifact storage is intended to support local filesystem and S3-compatible backends
(AWS S3, MinIO, etc.).

Possible deployment-level storage settings include:

- database URL environment reference;
- local artifact root;
- S3 endpoint;
- region;
- bucket;
- access-key environment reference;
- secret-key environment reference;
- TLS setting.

The exact nested key names are controlled by the current config/settings models.
Resolved credentials must never be serialized into the canonical experiment config.

---

## 13. `persistence`

Reserved for persistence-related experiment/application settings where the current config
model exposes them.

Operational PostgreSQL state includes:

- runs and immutable run config;
- target identity/capabilities;
- corpora/documents;
- benchmark cases;
- case executions;
- append-only attempts;
- target observations;
- artifact references;
- metric and aggregate results;
- structured errors.

Do not put runtime IDs, current status, timestamps, or attempt history into the test YAML.

---

## 14. `output`

Reserved for output/export/report configuration where exposed.

A conventional export layout is:

```text
exports/
└── <run-id>/
    ├── manifest.yaml
    ├── config.yaml
    ├── summary.json
    ├── cases.parquet
    ├── retrievals.parquet
    ├── metrics.parquet
    ├── traces.parquet
    └── errors.parquet
```

The CLI also accepts output paths directly for report/export commands, so this section may
be unnecessary in a given checkout.

---

## 15. `matrix`

Optional experiment matrix expansion.

```yaml
matrix:
  target.parameters.embedding_model:
    - "bge-m3"
    - "e5-large"

  target.parameters.chunk_size:
    - 256
    - 512

  target.parameters.top_k:
    - 5
    - 10
```

This produces the Cartesian product: `2 × 2 × 2 = 8` independent run configurations.

Rules:

- keys are dotted paths into the validated experiment config;
- each value is a list of alternatives;
- expansion order is deterministic;
- each expanded config is independently validated;
- each gets its own deterministic SHA-256 config hash;
- invalid paths must be rejected;
- semantically identical expanded configurations should not silently produce ambiguous
  identities.

A matrix is ideal for RAG parameter sweeps such as:

- `top_k`;
- chunk size/overlap;
- embedding model;
- reranker;
- generation model;
- prompt version;
- concurrency if you are deliberately testing evaluator/target performance.

---

## 16. Canonicalization and secrets

The evaluator creates a deterministic SHA-256 identity for the semantic configuration.

The hash should include settings that affect the experiment and exclude:

- resolved secrets;
- timestamps;
- ephemeral runtime state.

Equivalent YAML formatting or dictionary ordering should not change the hash.

Never store resolved credentials in:

- config hashes;
- persisted canonical configs;
- export manifests;
- logs;
- CLI output.

---

## 17. Separate API-level `TestDefinition`

The frontend/API layer also defines a higher-level reusable `TestDefinition` object. It is
different from the full YAML `ExperimentConfig`.

A `TestDefinition` contains:

```yaml
name: "My evaluation"
description: "Optional description"
target_id: "target-..."
benchmark_id: "benchmark-..."
metric_config_id: "metrics-..."
execution_config: {}
seed: 42
tags: []
metadata: {}
```

Its fields are:

| Field | Required | Type |
|---|---:|---|
| `name` | yes | string, 1-255 characters |
| `description` | no | string/null |
| `target_id` | yes | string |
| `benchmark_id` | yes | string |
| `metric_config_id` | yes | string |
| `execution_config` | no | object; defaults to `{}` |
| `seed` | no | integer/null |
| `tags` | no | list[string] |
| `metadata` | no | object |

This API-level object references separately registered target, benchmark, and metric
configuration records. In contrast, the experiment YAML is intended to describe a complete,
portable run configuration.

---

## 18. Metric-configuration API object

The API also exposes reusable metric configurations:

```yaml
name: "Default metrics"
mode: "all_available"
selected_metrics: []
metric_parameters: {}
judge_config: {}
retrieval_config: {}
metadata: {}
```

Fields:

| Field | Type |
|---|---|
| `name` | string |
| `mode` | `all_available` or `explicit` |
| `selected_metrics` | list[string] |
| `metric_parameters` | object |
| `judge_config` | object |
| `retrieval_config` | object |
| `metadata` | object |

---

## 19. Target-registration API object

The frontend/API target-registration schema exposes:

```yaml
name: "Local target"
version: "1"
implementation: "my-rag"
adapter: "http"
base_url: "http://localhost:8000"
python_target: null
authentication_env: null
corpus_mode: "DOCUMENTS"
parameters: {}
metadata: {}
```

Fields:

| Field | Type |
|---|---|
| `name` | string |
| `version` | string/null |
| `implementation` | string/null |
| `adapter` | `http` or `python` |
| `base_url` | string/null |
| `python_target` | string/null |
| `authentication_env` | string/null |
| `corpus_mode` | `DOCUMENTS`, `CHUNKS`, or `EXTERNAL` |
| `parameters` | object |
| `metadata` | object |

This is again an API resource schema, not necessarily identical to the portable experiment
YAML.

---

## 20. Recommended workflow

For a portable experiment file:

```bash
uv run rag-eval validate rag_eval_test_config.example.yaml
uv run rag-eval plan rag_eval_test_config.example.yaml
uv run rag-eval run rag_eval_test_config.example.yaml
```

Then, using the emitted run ID:

```bash
uv run rag-eval status <run-id>
uv run rag-eval score <run-id>
uv run rag-eval report <run-id>
```

The persisted canonical run configuration is authoritative for later resume/scoring/report
workflows.

---

## 21. Practical rule

When deciding where a parameter belongs:

- **describes benchmark truth/source data** → `dataset` / benchmark manifest;
- **changes the evaluated RAG system** → `target.parameters`;
- **changes how the evaluator calls the target** → `execution`;
- **changes what is measured** → `metrics`;
- **is a credential/storage endpoint** → environment-backed storage/auth settings;
- **creates a sweep** → `matrix`;
- **is only descriptive** → `tags` / `metadata`.

The most important extension point is `target.parameters`: it prevents `rag-eval` core from
hard-coding every possible RAG implementation detail.
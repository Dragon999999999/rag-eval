# rag-eval Architecture

## 1. Purpose

`rag-eval` is a modular evaluation framework for benchmarking RAG systems, retrievers, LLMs, and related retrieval/generation pipelines.

The evaluated system is the **target**. `rag-eval` is the **tester/evaluator**.

The normal execution model is:

```text
Benchmark / Dataset
        |
        v
    rag-eval
        |
        | HTTP or Python adapter
        v
      Target
 RAG / Retriever / LLM
        |
        v
Target Observation
        |
        v
 Metrics + Reports
```

The framework must support:

* retrieval evaluation;
* answer correctness evaluation;
* groundedness / faithfulness evaluation;
* citation evaluation;
* robustness evaluation;
* latency and throughput measurement;
* token and cost accounting;
* reliability and failure metrics;
* resumable benchmark execution;
* large datasets and large outputs;
* local and remote targets;
* future UI/API integration.

The framework must not depend on any particular RAG library.

---

# 2. Core Design Principles

## 2.1 Benchmark owns truth

`rag-eval` owns benchmark-controlled information:

* `Q`: original query;
* `H`: conversation history;
* `G`: gold/reference answer;
* `GE`: gold/reference evidence;
* benchmark document/corpus metadata;
* benchmark labels and tags.

The target must never be trusted to supply gold/reference information.

## 2.2 Target owns behavior

The target supplies observations of what it actually did:

* `A`: generated answer;
* `R`: retrieved chunks;
* `RM`: retrieval metadata;
* `C`: citations;
* `CONF`: confidence signals;
* target-side traces;
* target-side resource/token usage;
* target-side errors;
* effective target configuration.

## 2.3 Metrics operate on observations

Metrics consume benchmark data plus persisted target observations.

Metric computation must be independent from target execution whenever possible.

An existing successful target execution must be reusable for:

* new metrics;
* fixed metric implementations;
* new judge models;
* new report formats.

Running `rag-eval score <run-id>` must not query the evaluated target again.

## 2.4 Missing information is not failure

Targets expose capabilities.

If a target does not expose information needed for a metric, the metric result must be:

```text
UNAVAILABLE_MISSING_INPUT
```

not `0`, not `NaN`, and not a failed benchmark case.

## 2.5 Preserve raw observations

Never persist only aggregate metrics.

Preserve enough raw information to calculate new metrics later.

Important examples:

* raw target request;
* raw target response;
* streaming events;
* retrieved texts;
* retrieval scores/ranks;
* citations;
* traces;
* usage;
* errors.

## 2.6 Large data does not belong in PostgreSQL

PostgreSQL stores transactional state and metadata.

Large artifacts belong in object storage.

Analytical bulk output belongs in Parquet.

---

# 3. Technology Stack

Use the following default stack unless there is a concrete technical reason to change it.

| Concern                 | Technology             |
| ----------------------- | ---------------------- |
| Language                | Python                 |
| Package management      | `uv`                   |
| Data models             | Pydantic v2            |
| CLI                     | Typer                  |
| HTTP client             | async `httpx`          |
| Database                | PostgreSQL             |
| ORM                     | SQLAlchemy 2 async     |
| PostgreSQL driver       | `asyncpg`              |
| Migrations              | Alembic                |
| Artifact storage        | S3-compatible storage  |
| Local S3 implementation | MinIO                  |
| Large analytical files  | Apache Parquet         |
| Parquet library         | PyArrow                |
| Local analytics         | DuckDB                 |
| Config files            | YAML                   |
| Retry/backoff           | Tenacity or equivalent |
| Testing                 | pytest                 |
| Runtime                 | Docker                 |
| Local infrastructure    | Docker Compose         |

A future UI may use:

```text
FastAPI + React
```

but no UI is required for the initial framework.

---

# 4. Repository Structure

Preferred structure:

```text
rag-eval/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RESILIENCE.md
│   └── TARGET_PROTOCOL_V1.md
│
├── src/
│   └── rag_eval/
│       ├── adapters/
│       ├── artifacts/
│       ├── cli/
│       ├── config/
│       ├── datasets/
│       ├── db/
│       ├── execution/
│       ├── judges/
│       ├── metrics/
│       ├── models/
│       ├── reporting/
│       └── services/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── examples/
```

Do not create unrelated layers merely to match this tree. Prefer simple modules where possible.

---

# 5. Canonical Data Flow

The primary flow is:

```text
Dataset
   |
   | Q, H, G, GE, documents
   v
rag-eval execution engine
   |
   | canonical request
   v
TargetAdapter
   |
   | Python or HTTP
   v
Target
   |
   | A, R, RM, C, TRACE, USAGE, ERR, CONF
   v
TargetObservation
   |
   +----> durable persistence
   |
   v
Metric engine
   |
   v
MetricResult
   |
   v
Aggregation / report / Parquet export
```

The `TargetObservation` is the central persisted representation of an executed target request.

---

# 6. Canonical Information Model

The core information categories are:

| Code    | Meaning                     |
| ------- | --------------------------- |
| `Q`     | Original user query         |
| `H`     | Conversation history        |
| `A`     | Actual generated answer     |
| `G`     | Gold/reference answer       |
| `R`     | Ranked retrieved chunks     |
| `RM`    | Retrieval metadata          |
| `GE`    | Gold/reference evidence     |
| `C`     | Citations                   |
| `D`     | Corpus/document metadata    |
| `CFG`   | Configuration               |
| `TRACE` | Stage-level execution trace |
| `USAGE` | Token/API/resource usage    |
| `ERR`   | Errors/retries/failures     |
| `CONF`  | Confidence signals          |

The concrete Pydantic models are the authoritative executable definition once implemented.

Documentation must not duplicate every model field.

---

# 7. Source of Truth Hierarchy

Once implemented, use this hierarchy:

```text
Conceptual architecture:
    docs/ARCHITECTURE.md

Failure/recovery semantics:
    docs/RESILIENCE.md

External target protocol:
    docs/TARGET_PROTOCOL_V1.md

Protocol/data structures:
    Pydantic models

Persistence structure:
    SQLAlchemy models + Alembic migrations

Experiment configuration:
    Pydantic configuration models
```

If documentation and executable schemas disagree, fix the disagreement rather than maintaining two incompatible definitions.

---

# 8. Benchmark Data Model

A benchmark contains:

```text
Benchmark
├── manifest
├── corpus/documents
└── cases
```

A benchmark case conceptually contains:

```text
case_id
query
history
reference_answer
gold_evidence
answerability
tags
difficulty
language
metadata
```

`query` and `history` are supplied to the target.

`reference_answer` and `gold_evidence` are never supplied unless explicitly required for a controlled experiment.

---

# 9. Gold Evidence

Gold relevance must not depend on target chunk IDs.

Gold evidence should identify source evidence using stable source coordinates such as:

```text
document_id
page
start_char
end_char
text
```

This permits fair comparison between:

```text
chunk_size = 256
chunk_size = 512
chunk_size = 1024
```

even though all produce different chunk IDs.

---

# 10. Retrieval Representation

Retrieval is modeled as one or more ordered stages.

Example:

```text
dense_candidates
      |
      v
hybrid_fusion
      |
      v
reranking
      |
      v
final_context
```

Each stage contains ranked retrieved items.

A retrieved item may contain:

```text
retrieval_id
text
rank

source:
    document_id
    chunk_id
    page
    character span

score:
    value
    score type

metadata
```

Score semantics must be explicit.

Examples:

```text
cosine_similarity
dot_product
bm25
rrf
cross_encoder
custom
```

Do not assume scores from different scoring methods are directly comparable.

---

# 11. Final Context

`FINAL_CONTEXT` has special meaning:

> It represents the evidence actually supplied to the generation model.

This differs from retrieved candidates.

Example:

```text
50 dense candidates
20 reranked results
5 final-context chunks
```

Retrieval metrics can evaluate earlier stages.

Groundedness normally evaluates the final generation context.

---

# 12. Target Adapter

All evaluated systems are accessed through a canonical `TargetAdapter`.

Required conceptual operations:

```text
capabilities()
health()

create_corpus()
delete_corpus()

upload_document()
upload_chunks()
get_operation()

retrieve()

query()
stream_query()

recover_request()
```

Individual operations are capability-dependent.

Unsupported operations must produce normalized capability errors rather than arbitrary implementation exceptions.

---

# 13. Adapter Implementations

Initial adapters:

```text
PythonTargetAdapter
HttpTargetAdapter
```

Both return the same canonical Pydantic models.

The execution engine must not contain HTTP-specific or Python-target-specific logic.

Future adapters may include:

```text
GenericRestAdapter
gRPC adapter
OpenAI-compatible adapter
```

without changing the metric engine.

---

# 14. Target Capability Model

Targets may expose only part of the protocol.

Examples:

```text
plain LLM:
    query

grounded LLM:
    query
    supplied contexts

basic RAG:
    query
    retrieval observations

retriever:
    retrieve

full RAG:
    document ingestion
    retrieval
    query

observable RAG:
    traces
    usage
    citations

resilient RAG:
    idempotency
    request recovery
```

The evaluator must discover capabilities before execution.

Metric availability is derived from:

```text
benchmark data
+
target capabilities
+
actual observation fields
```

---

# 15. Corpus Modes

Support three primary corpus modes.

## DOCUMENTS

The evaluator supplies source files:

```text
PDF
TXT
DOCX
...
```

The target performs:

```text
extraction
chunking
embedding
indexing
```

Use this when benchmarking the complete RAG pipeline.

## CHUNKS

The evaluator supplies canonical chunks.

The target performs downstream processing such as embedding/indexing.

Use this to compare retrieval systems while keeping chunking fixed.

## EXTERNAL

The target already owns the corpus.

The evaluator supplies only queries and an external corpus identifier where applicable.

Some ingestion-related metrics are unavailable.

---

# 16. Query Context Modes

Query execution supports:

```text
TARGET_RETRIEVAL
SUPPLIED_CONTEXT
NO_CONTEXT
```

## TARGET_RETRIEVAL

Normal RAG:

```text
Q -> target retrieval -> generation
```

## SUPPLIED_CONTEXT

Evaluator controls evidence:

```text
Q + evaluator contexts -> target generation
```

Useful for:

* faithfulness tests;
* noise robustness;
* counterfactual tests;
* hallucination tests;
* plain LLM grounding evaluation.

## NO_CONTEXT

Plain model evaluation:

```text
Q -> model
```

---

# 17. Persistence Architecture

Use:

```text
PostgreSQL
+
S3 / MinIO
+
Parquet
```

Each has a different responsibility.

## PostgreSQL

Transactional and operational state:

```text
runs
configs
targets
capabilities
corpora
documents
benchmark cases
case executions
attempts
stage executions
target observations
artifact references
metric results
aggregate results
errors
```

Do not store large raw responses or PDFs directly in PostgreSQL.

## S3 / MinIO

Large immutable artifacts:

```text
source PDFs
raw requests
raw responses
stream events
large judge inputs
large judge outputs
logs
large diagnostic artifacts
```

Artifacts should have:

```text
artifact_id
URI
SHA-256
size
content type
timestamp
```

## Parquet

Portable analytical output:

```text
cases.parquet
retrievals.parquet
metrics.parquet
traces.parquet
errors.parquet
```

Parquet is not the transactional source of truth while a run is active.

---

# 18. Run Model

Conceptually:

```text
Run
└── CaseExecution
    └── Attempt
```

A benchmark case may require multiple attempts because of:

```text
rate limits
timeouts
connection failures
provider failures
process crashes
```

Attempts are append-only.

Never overwrite an earlier attempt.

---

# 19. Target Observation

A successful or partially successful target execution should normalize into a `TargetObservation`.

Conceptually:

```text
TargetObservation
├── case_id
├── request_id
├── answer
├── retrieval stages
├── citations
├── confidence
├── trace
├── usage
├── errors/warnings
├── requested configuration
├── effective configuration
├── raw request reference
└── raw response reference
```

Target observations should become immutable after normalization.

Metric results are derived from them.

---

# 20. Metrics Architecture

Metrics are plugins/modules rather than hardcoded orchestration behavior.

Each metric declares:

```text
metric_id
metric_version
scope
required inputs
optional inputs
judge requirement
```

Example:

```text
Recall@K:
    requires R + GE

Faithfulness:
    requires A + FINAL_CONTEXT + semantic judge

Citation resolution:
    requires C + D

Confidence calibration:
    requires CONF + correctness label
```

Metric result states:

```text
COMPUTED
UNAVAILABLE_MISSING_INPUT
NOT_APPLICABLE
FAILED
SKIPPED
```

Never silently convert unavailable metrics into zero.

---

# 21. Metric Categories

The architecture must support metrics from at least:

```text
answer correctness
answer relevance
answer completeness

groundedness / faithfulness
hallucination
contradiction

citation quality
citation provenance

retrieval
ranking
reranking
context construction

robustness
abstention
noise sensitivity
multi-hop reasoning

latency
throughput

tokens
cost

CPU
RAM
GPU
VRAM

reliability
failures
retries

cache behavior

multi-turn conversations

evaluation-system quality
```

Not all must be implemented initially.

---

# 22. Judge Architecture

Semantic metrics may require model-based judging.

Judges must use a separate abstraction:

```text
JudgeAdapter
```

Do not mix judge calls into target adapters.

Judge outputs should be persisted like other expensive calls.

Important intermediate representations may include:

```text
Claim
ClaimAssessment
EvidenceAssessment
```

A future judge-model change must not require rerunning the evaluated target.

---

# 23. Configuration

Runs are defined declaratively using YAML.

Main sections:

```text
version

run
dataset
target
execution
metrics
storage
persistence
output
```

Configurations must be validated with Pydantic before execution.

Secrets must be referenced from environment variables or secret providers.

Secrets must not be written into:

```text
run manifests
logs
Parquet files
raw persisted configuration
```

Configuration should support experiment matrices.

Example dimensions:

```text
embedding model
chunk size
overlap
top_k
reranker
retrieval algorithm
generation model
prompt version
```

Each matrix combination becomes an independently identifiable run.

---

# 24. Configuration Reproducibility

Every run should record enough information to identify:

```text
rag-eval version
rag-eval git commit

target version if available
target git commit if available

benchmark version
benchmark hash

requested target configuration
effective target configuration

metric versions
judge versions

Docker image digest where applicable

random seed
```

Run configuration should have a deterministic canonical hash.

---

# 25. CLI

The initial product is CLI-first.

Expected command surface:

```text
rag-eval validate CONFIG
rag-eval plan CONFIG

rag-eval target capabilities CONFIG

rag-eval corpus prepare CONFIG

rag-eval run CONFIG
rag-eval resume RUN_ID
rag-eval status RUN_ID

rag-eval score RUN_ID

rag-eval report RUN_ID
rag-eval compare RUN_ID RUN_ID
```

`validate` and `plan` perform no expensive evaluation work.

`score` must operate only from persisted observations.

---

# 26. Reporting

Reports should initially support:

```text
terminal
JSON
Parquet
```

Reports should distinguish:

```text
metric unavailable
metric failed
metric computed as zero
```

These are semantically different states.

Do not collapse all quality dimensions into a single mandatory "RAG score".

Individual metric dimensions must remain accessible.

---

# 27. Testing Strategy

Use:

```text
tests/unit
tests/integration
tests/e2e
```

Unit tests:

```text
models
metrics
configuration
state transitions
normalizers
```

Integration tests:

```text
PostgreSQL
MinIO
HTTP adapter
artifact persistence
Alembic migrations
```

End-to-end tests:

```text
benchmark
→ target
→ observation
→ metrics
→ report
```

A deterministic mock target should eventually support:

```text
success
retrieval
citations
streaming

429
timeout
500
malformed responses
connection loss

idempotency
request recovery
```

---

# 28. Performance Measurement

Client-observed timing and target-reported timing are separate.

Client-side examples:

```text
total HTTP latency
TTFB
TTFT
inter-token latency
E2E latency
```

Target-side examples:

```text
embedding
retrieval
fusion
reranking
generation
postprocessing
```

Target tracing should use arbitrary hierarchical spans rather than fixed timing fields.

This permits future architectures without schema redesign.

---

# 29. OpenTelemetry Compatibility

Trace representation should be conceptually compatible with OpenTelemetry:

```text
trace_id
span_id
parent_span_id
name
start
end/duration
attributes
```

The project does not need to require an OpenTelemetry backend initially.

---

# 30. Development Rules

Prefer simple production-ready implementations.

Do not:

* create temporary SQLite architecture;
* create in-memory production persistence;
* couple metrics directly to HTTP;
* couple orchestration to one RAG;
* store large blobs in PostgreSQL;
* rerun successful target calls unnecessarily;
* treat missing capability as metric score zero;
* hardcode retrieval to a single stage;
* use target chunk IDs as gold evidence;
* silently mutate historical attempts;
* make MLflow or another third-party evaluation framework the core architecture.

External libraries such as RAGAS, DeepEval, MLflow, or other evaluation tools may later be integrated as adapters/providers.

`rag-eval` owns its canonical data model and run state.

---

# 31. Architectural Change Policy

Agents should follow this architecture unless implementation reveals a concrete contradiction.

For minor implementation choices, agents may choose the simplest reasonable solution.

For changes affecting any of the following, preserve compatibility or explicitly update canonical documentation:

```text
TargetAdapter contract
Target Protocol
TargetObservation
benchmark evidence representation
run/attempt model
persistence ordering
resilience semantics
metric-status semantics
storage responsibility boundaries
```

Avoid broad redesigns during unrelated implementation tasks.

---

# 32. Initial Definition of Done

The initial `rag-eval` foundation is complete when this works:

```bash
docker compose up -d

rag-eval validate examples/basic.yaml
rag-eval plan examples/basic.yaml

rag-eval run examples/basic.yaml

rag-eval status <run-id>
rag-eval report <run-id>
```

and the system supports:

```text
canonical benchmark cases
HTTP and Python targets
document/chunk corpus modes
independent retrieval
full query execution
durable target observations
retries/resume
deterministic metrics
Parquet exports
```

without requiring architectural replacement for the next phase of public-dataset integration.

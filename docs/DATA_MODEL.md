# rag-eval Data Model

## 1. Purpose

This document defines the conceptual data model used throughout `rag-eval`.

It exists primarily to establish terminology and relationships before the canonical Pydantic models are implemented.

After canonical Pydantic models exist:

> The Pydantic models are the authoritative executable data-model specification.

Agents should then use this document only for architectural orientation.

---

# 2. Design Principles

The data model must:

* distinguish benchmark truth from target observations;
* support incomplete target capabilities;
* support both RAG and plain LLM evaluation;
* support multi-stage retrieval;
* preserve raw observations;
* support resumable execution;
* avoid coupling gold evidence to target chunking;
* distinguish target execution from metric calculation;
* support large datasets without forcing large values into PostgreSQL;
* allow old observations to be re-scored later.

---

# 3. Core Information Categories

Canonical conceptual information:

| Code    | Meaning                  | Typical owner       |
| ------- | ------------------------ | ------------------- |
| `Q`     | Original query           | benchmark           |
| `H`     | Conversation history     | benchmark           |
| `A`     | Actual answer            | target              |
| `G`     | Gold/reference answer    | benchmark           |
| `R`     | Retrieved items          | target              |
| `RM`    | Retrieval metadata       | target              |
| `GE`    | Gold evidence            | benchmark           |
| `C`     | Citations                | target              |
| `D`     | Document/corpus metadata | benchmark/evaluator |
| `CFG`   | Configuration            | evaluator + target  |
| `TRACE` | Stage execution trace    | evaluator + target  |
| `USAGE` | Tokens/cost/resources    | evaluator + target  |
| `ERR`   | Errors and failures      | evaluator + target  |
| `CONF`  | Confidence signals       | target              |

---

# 4. High-Level Entity Graph

Conceptually:

```text
Benchmark
├── Corpus
│   └── Document
│       └── optional evaluator-defined Chunk
│
└── BenchmarkCase
    ├── Query
    ├── History
    ├── ReferenceAnswer
    └── GoldEvidence[]


Run
├── Configuration
├── Target
├── Benchmark reference
│
└── CaseExecution[]
    └── Attempt[]
        ├── Request
        ├── RawResponse
        ├── TargetObservation
        └── Error[]


TargetObservation
├── Answer
│   └── Citation[]
├── RetrievalResult
│   └── RetrievalStage[]
│       └── RetrievedItem[]
├── Confidence[]
├── Trace
├── Usage
└── Configuration


Evaluation
├── MetricResult[]
├── ClaimAssessment[]
└── EvidenceAssessment[]
```

---

# 5. Benchmark

A benchmark is a versioned collection of:

```text
manifest
corpus
benchmark cases
metadata
```

Conceptual fields:

```text
benchmark_id
name
version
schema_version

content_hash

corpus reference

number of cases

tags
metadata
```

The benchmark must be identifiable independently from a particular target.

---

# 6. Benchmark Manifest

The manifest should record enough information to reproduce benchmark identity.

Conceptually:

```text
benchmark_id
name
version

schema_version

sha256/content digest

case count

corpus identity

created_at

source/provenance

metadata
```

The benchmark manifest may point to files in object storage rather than containing all benchmark contents directly.

---

# 7. Benchmark Case

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

Minimal useful case:

```text
case_id
query
```

Other fields are optional depending on the intended metrics.

---

# 8. Query

The query represents the direct user input to evaluate.

Conceptually:

```text
text
metadata
```

Usually represented directly as a string in the benchmark case unless a richer query model is required.

The evaluator supplies the query to the target.

---

# 9. Conversation History

History is an ordered list of messages.

Message concept:

```text
role
content
name optional
metadata
```

Canonical roles:

```text
system
user
assistant
tool
```

History is benchmark-controlled input.

---

# 10. Reference Answer

The reference answer is benchmark truth used for correctness/completeness evaluation.

It may be:

```text
single canonical answer
multiple acceptable answers
structured expected values
claim list
```

The initial implementation may use:

```text
reference_answer: string | null
```

and later extend where required.

A reference answer is not normally sent to the target.

---

# 11. Answerability

Useful conceptual states:

```text
ANSWERABLE
UNANSWERABLE
AMBIGUOUS
UNKNOWN
```

This permits evaluation of:

```text
abstention
negative rejection
hallucination on unavailable evidence
```

---

# 12. Gold Evidence

Gold evidence represents evidence that should support the reference answer.

It must be stable across target chunking strategies.

Conceptual entity:

```text
EvidenceSpan
```

Fields may include:

```text
evidence_id

document_id
page

start_char
end_char

text

relevance

metadata
```

Gold evidence must not use target-generated chunk IDs as its primary identity.

---

# 13. Gold Evidence Matching

Retrieved evidence may be considered relevant by matching:

```text
document identity
page
character span overlap
text overlap
semantic evidence equivalence
```

depending on metric implementation.

Deterministic span/document matching should be preferred where reliable annotations exist.

---

# 14. Corpus

A corpus represents the set of source material used by a benchmark or run.

Conceptual fields:

```text
corpus_id
name
version
content_hash

mode

documents
optional chunks

metadata
```

Corpus modes:

```text
DOCUMENTS
CHUNKS
EXTERNAL
```

---

# 15. Document

Conceptual fields:

```text
document_id

filename
mime_type

sha256
size_bytes

artifact reference

metadata
```

Optional metadata may include:

```text
title
author
publication date
source URL
language
tags
```

`document_id` should remain stable throughout ingestion, retrieval, and citation processing.

---

# 16. Artifact Reference

Large values should be represented using artifact references.

Conceptually:

```text
artifact_id

uri

sha256
size_bytes
content_type

created_at

metadata
```

The bytes themselves normally live in:

```text
S3
MinIO
local artifact store
```

rather than PostgreSQL.

---

# 17. Chunk

A canonical evaluator-defined chunk may contain:

```text
chunk_id
document_id

text

source location

metadata
```

Evaluator-defined chunks are used primarily for controlled `CHUNKS` corpus mode.

Target-generated chunks are observations and may differ.

---

# 18. Source Location

Common representation for:

```text
gold evidence
chunks
retrieval
citations
supplied contexts
```

Conceptual fields:

```text
document_id

chunk_id optional

page optional

start_char optional
end_char optional

section optional

metadata
```

Unavailable values remain null/absent.

Never invent coordinates.

---

# 19. Run

A run represents one benchmark evaluation under one immutable effective experiment definition.

Conceptual fields:

```text
run_id

name

status

benchmark identity

target identity

config identity/hash

rag-eval version
rag-eval git commit

created_at
started_at
finished_at

seed

tags
metadata
```

A materially changed experiment configuration should produce a new run.

---

# 20. Configuration

Run configuration has at least two important forms:

```text
requested configuration
effective target configuration
```

Requested configuration is what `rag-eval` asked for.

Effective configuration is what the target reports actually using.

Conceptually:

```text
requested
effective
configuration_hash
```

Do not silently overwrite requested values with effective values.

---

# 21. Target

Conceptual target identity:

```text
target_id

name
version

adapter type

endpoint/import path

capabilities

metadata
```

Secrets are not persisted as target metadata.

---

# 22. Target Capabilities

Capabilities describe which observations/operations are available.

Conceptual groups:

```text
query

streaming
conversation history

retrieval
retrieval stages

document ingestion
chunk ingestion
context injection

citations
confidence

target trace

usage:
    tokens
    cost
    CPU
    RAM
    GPU
    VRAM

retrieval metadata:
    score
    rank
    document ID
    chunk ID
    page
    span

effective configuration

idempotency
request recovery
```

Capabilities are descriptive, not quality metrics.

---

# 23. Case Execution

Represents execution of one benchmark case within one run.

Conceptual fields:

```text
case_execution_id

run_id
case_id

status

current attempt number

created_at
updated_at

metadata
```

One case execution may contain multiple attempts.

---

# 24. Attempt

Represents one execution attempt of an expensive logical operation.

Conceptual fields:

```text
attempt_id

case_execution_id

attempt_number

request_id
idempotency_key
canonical_request_hash

status

started_at
finished_at

raw request artifact
raw response artifact

target observation reference

error references

metadata
```

Attempts are append-only historical records.

---

# 25. Request

Canonical request identity/metadata:

```text
request_id

request type

canonical payload

canonical payload hash

idempotency key

created_at
```

The complete raw request may be stored as an artifact.

---

# 26. Target Observation

The central representation of what the target did.

Conceptually:

```text
TargetObservation

observation_id

case_id
request_id

answer

retrieval

confidence

trace

usage

warnings
errors

requested configuration
effective configuration

raw request artifact
raw response artifact

normalization version

created_at
```

Once durably normalized, historical observations should not be mutated.

---

# 27. Answer

Conceptual fields:

```text
text

finish_reason

citations

structured_output optional

metadata
```

Finish reason examples:

```text
STOP
LENGTH
REFUSAL
CONTENT_FILTER
ERROR
CANCELLED
UNKNOWN
```

Partial answers should be retained rather than discarded.

---

# 28. Structured Output

Some targets may return:

```text
JSON
typed objects
classification results
tool outputs
```

The canonical answer may therefore include:

```text
structured_output
```

alongside human-readable text.

This remains optional.

---

# 29. Citation

Conceptual fields:

```text
citation_id

display text

answer span

source location

retrieval_id optional

metadata
```

A citation may therefore link:

```text
answer claim
   |
citation
   |
retrieved item
   |
document/page/span
```

This relationship supports citation-quality metrics.

---

# 30. Answer Span

Conceptual fields:

```text
start_char
end_char
```

An answer span identifies the portion of generated answer supported by a citation.

It is optional because some targets cannot provide precise mapping.

---

# 31. Retrieval Result

Conceptually:

```text
RetrievalResult
└── RetrievalStage[]
```

There may be zero stages for targets that do not expose retrieval.

---

# 32. Retrieval Stage

Conceptual fields:

```text
stage_id

parent_stage_id optional

type

items

metadata
```

Canonical stage types:

```text
CANDIDATE_RETRIEVAL
FUSION
RERANK
FILTER
COMPRESSION
FINAL_CONTEXT
CUSTOM
```

Stages represent transformation of retrieval evidence through the pipeline.

---

# 33. Retrieved Item

Conceptual fields:

```text
retrieval_id

rank

text

source

score

metadata
```

`rank` is stage-specific.

The same source chunk may appear in several stages with different ranks/scores.

---

# 34. Retrieval Score

Conceptual fields:

```text
value
type
metadata
```

Examples:

```text
cosine_similarity
dot_product
bm25
rrf
cross_encoder
custom
```

A numerical score without semantics should not be treated as directly comparable across systems.

---

# 35. Confidence Signal

Targets may return multiple confidence values.

Conceptual fields:

```text
name

value

minimum
maximum

semantics

metadata
```

Examples:

```text
answer confidence
retrieval confidence
probability of correctness
probability of support
```

Confidence is optional.

---

# 36. Trace

Trace concept:

```text
Trace
├── trace_id
└── TraceSpan[]
```

Trace representation should be compatible in spirit with OpenTelemetry.

---

# 37. Trace Span

Conceptual fields:

```text
span_id
parent_span_id

name

started_at
ended_at
duration

attributes
```

Example hierarchy:

```text
query
├── embedding
├── retrieval
│   ├── dense search
│   └── BM25
├── fusion
├── reranking
├── prompt build
├── generation
└── citation mapping
```

Arbitrary future stage names must remain possible.

---

# 38. Usage

Usage may describe:

```text
tokens
API calls
cost
CPU
RAM
GPU
VRAM
network
```

Conceptual structure:

```text
Usage

tokens:
    input
    output
    total
    retrieved_context
    embedding

calls:
    LLM
    embedding
    retrieval
    reranker

cost:
    value
    currency

resources:
    cpu_time
    cpu_peak
    ram_peak

    gpu_time
    gpu_peak
    vram_peak

network:
    bytes_sent
    bytes_received
```

All fields are optional.

---

# 39. Error Record

Errors must be structured.

Conceptual fields:

```text
error_id

category
code

message

stage

retryable

retry_after

HTTP status

provider:
    name
    status
    code

exception type optional

timestamp

raw artifact reference optional

details
```

Canonical categories are defined in `TARGET_PROTOCOL_V1.md` and `RESILIENCE.md`.

---

# 40. Warning

Warnings represent non-fatal target or evaluator observations.

Conceptually:

```text
code
message
stage
metadata
```

Example:

```text
requested top_k=10 but target returned 8
```

Warnings should not automatically fail a case.

---

# 41. Operation

Represents asynchronous work such as indexing.

Conceptual fields:

```text
operation_id

kind

status

progress

started_at
finished_at

result

error
```

Typical kinds:

```text
DOCUMENT_INGESTION
CHUNK_INGESTION
INDEX_BUILD
CORPUS_DELETE
CUSTOM
```

---

# 42. Operation Progress

Conceptual fields:

```text
value
stage
current
total
message
```

All optional.

Progress is informational and must not be required for asynchronous support.

---

# 43. Query Request

Conceptually:

```text
request_id

corpus_id optional

query
history

context_policy

supplied_contexts

parameters

include options

stream
```

Context policies:

```text
TARGET_RETRIEVAL
SUPPLIED_CONTEXT
NO_CONTEXT
```

---

# 44. Supplied Context

Conceptual fields:

```text
context_id

text

source location optional

metadata
```

Supplied contexts are evaluator-controlled inputs.

They are not target retrieval results.

---

# 45. Retrieve Request

Conceptually:

```text
request_id

corpus_id

query
history

parameters
filters

include options
```

Retrieval calls must not require answer generation.

---

# 46. Query/Request Include Options

Requests may ask targets for optional observations.

Examples:

```text
retrieval
retrieval stages
citations
confidence
trace
usage
effective configuration
raw prompt
```

Targets may decline unsupported fields based on capabilities.

---

# 47. Metric Result

Conceptual fields:

```text
metric_result_id

run_id
case_id optional

metric_id
metric_version

value

status
reason

details

evaluator metadata

created_at
```

Status values:

```text
COMPUTED
UNAVAILABLE_MISSING_INPUT
NOT_APPLICABLE
FAILED
SKIPPED
```

---

# 48. Metric Value

Metric values may be:

```text
float
integer
boolean
string/category
null
```

Null does not imply zero.

If value is null, status/reason must explain why.

---

# 49. Aggregate Metric Result

Run-level metric aggregation is distinct from case-level results.

Conceptual fields:

```text
metric_id
metric_version

aggregation

value

sample_count
available_count
failed_count

distribution statistics

metadata
```

Useful aggregations:

```text
mean
median
min
max
std

p50
p75
p90
p95
p99

count
rate
```

---

# 50. Metric Requirements

Each metric implementation should declare:

```text
required benchmark inputs
required observation inputs
required target capabilities
judge requirement
scope
```

Example:

```text
Recall@K

requires:
    retrieved items
    gold evidence
```

Example:

```text
Faithfulness

requires:
    answer
    final context
    semantic evaluator
```

---

# 51. Claim

Semantic evaluation may decompose answers/references into claims.

Conceptual fields:

```text
claim_id

text

source:
    answer
    reference
    evidence

answer span optional

metadata
```

Claims are derived evaluation objects, not target truth.

---

# 52. Claim Assessment

Conceptually:

```text
claim_id

classification

supporting evidence
contradicting evidence

score/confidence optional

judge metadata
```

Possible classifications:

```text
SUPPORTED
CONTRADICTED
UNSUPPORTED
UNKNOWN
```

This representation may power:

```text
faithfulness
hallucination rate
contradiction rate
grounded correctness
```

---

# 53. Evidence Assessment

Conceptually:

```text
claim_id
evidence reference

relationship

score/confidence

judge metadata
```

Relationships may include:

```text
ENTAILS
CONTRADICTS
NEUTRAL
UNKNOWN
```

---

# 54. Judge Execution

A semantic judge call is itself an expensive execution.

Conceptually it may have:

```text
judge_request_id

judge model/config

input artifact

attempts

raw response artifact

normalized result

usage
cost
errors
```

Judge failures must not invalidate target observations.

---

# 55. Dataset Adapter

Future public benchmarks should normalize into the canonical benchmark model.

Conceptual interface:

```text
load manifest
load corpus/documents
iterate benchmark cases
validate
```

Dataset-specific structures should not leak into core metric/execution logic.

---

# 56. Artifact Types

Useful artifact categories:

```text
SOURCE_DOCUMENT

RAW_TARGET_REQUEST
RAW_TARGET_RESPONSE

STREAM_EVENTS

RAW_JUDGE_REQUEST
RAW_JUDGE_RESPONSE

LOG

PARQUET_EXPORT

REPORT

OTHER
```

Artifact category should not be inferred only from filename.

---

# 57. Persistence Separation

Canonical responsibilities:

```text
PostgreSQL
    transactional state
    relational metadata
    execution state
    metric records
    artifact pointers

S3 / MinIO
    large immutable bytes

Parquet
    portable analytical tables
```

Do not attempt to make one storage layer serve all three responsibilities.

---

# 58. Database Relationship Overview

Approximate logical tables/entities:

```text
runs
run_configs

targets
target_capabilities

benchmarks
benchmark_cases

corpora
documents

case_executions
attempts
stage_executions

target_observations

artifacts

metric_results
aggregate_metric_results

errors

optional:
judge_executions
operations
```

The exact SQL schema is authoritative once implemented.

---

# 59. Raw vs Normalized Data

Always distinguish:

```text
raw target response
```

from:

```text
normalized TargetObservation
```

A parser bug should not destroy or overwrite raw data.

Normalization may have a version field.

Example:

```text
normalization_version = 1
```

Future normalization logic may produce a new normalized representation from the same raw artifact.

---

# 60. Immutability

Prefer immutable historical records for:

```text
run configuration
attempts
raw artifacts
target observations
metric results/versioned scoring
```

State fields may evolve as execution progresses.

Historical evidence of what occurred must not be rewritten.

---

# 61. Versioning

Version at least:

```text
benchmark
dataset schema

protocol
canonical model/schema

metric implementation

judge rubric

normalizer

rag-eval application
```

This allows old results to remain interpretable after the framework evolves.

---

# 62. Content Hashing

Use SHA-256 or equivalent strong content hashing for important reproducibility objects:

```text
documents
benchmark manifests
canonical configs
raw artifacts
request payloads
```

Filename alone is not identity.

---

# 63. Client Timing Data

Client-side timing is evaluator-generated observation.

Conceptually:

```text
request start
connection timing where available
time to first byte
time to first token
stream-event timestamps
request end
```

Derived metrics should be calculated from raw timestamps where practical.

---

# 64. Server Timing Data

Target-reported trace data remains separate.

Never merge:

```text
client E2E latency
```

with:

```text
target internal query duration
```

into one indistinguishable field.

---

# 65. Resource Monitoring

Resource information may originate from:

```text
target self-reporting
evaluator-side process/container monitoring
external telemetry
```

The source of measurement should be recorded.

Do not assume target-reported and externally measured utilization are equivalent.

---

# 66. External Corpus Identity

For `EXTERNAL` corpus mode, useful fields may include:

```text
external_corpus_id

external_version

external_hash if available

description
metadata
```

If exact corpus reproducibility cannot be verified, reports should retain that limitation.

---

# 67. Metric Scope

Metrics may operate at:

```text
retrieval item
retrieval stage
claim
case
conversation
run
benchmark
```

Metric implementations should declare their scope.

---

# 68. Multi-Turn Data

A future conversational benchmark may model:

```text
ConversationCase
└── Turn[]
```

Each turn may contain:

```text
query
history
reference answer
gold evidence
target observation
metrics
```

The initial implementation may represent each benchmark case using query + history without introducing a separate complex conversation hierarchy.

Avoid premature complexity.

---

# 69. Extensibility Fields

Use controlled extension locations such as:

```text
metadata
attributes
details
```

for target/dataset-specific values.

Avoid polluting canonical top-level models with one-project-specific fields.

---

# 70. Missing Data

Missing information must remain distinguishable from actual values.

Examples:

```text
confidence missing
    != confidence = 0

no citation support
    != zero correct citations

retrieval unavailable
    != retrieval returned zero results
```

This distinction is fundamental to metric correctness.

---

# 71. Empty vs Missing

Examples:

```text
retrieval = null
```

may mean:

```text
target does not expose retrieval
```

while:

```text
retrieval.stages = [
    final_context(items=[])
]
```

means:

```text
retrieval executed and returned nothing
```

These must not be treated identically.

---

# 72. Error vs Valid Negative Result

Examples of valid target behavior:

```text
zero retrieved chunks
model refusal
abstention
"I don't know"
no citation emitted
```

These are observations.

Examples of execution errors:

```text
timeout
HTTP 500
invalid protocol response
connection failure
```

The data model must preserve the distinction.

---

# 73. Initial Pydantic Model Set

The first canonical model implementation should cover approximately:

```text
TargetInfo
TargetCapabilities
HealthStatus

SourceLocation
ArtifactRef

Message

Document
Chunk
EvidenceSpan
SuppliedContext

Answer
Citation
ConfidenceSignal

RetrievalScore
RetrievedItem
RetrievalStage
RetrievalResult

TraceSpan
Trace
Usage

ErrorRecord
WarningRecord

Operation
OperationProgress

CreateCorpusRequest
CreateCorpusResponse

RetrieveRequest
RetrieveResponse

QueryRequest
QueryResponse
QueryEvent

RequestRecoveryResult

TargetObservation

BenchmarkManifest
BenchmarkCase

MetricResult
AggregateMetricResult

Claim
ClaimAssessment
EvidenceAssessment
```

Exact module organization is an implementation choice.

---

# 74. Model Validation Principles

Prefer:

```text
strict validation
explicit enums
timezone-aware datetime
non-negative counts/durations
valid span boundaries
rank >= 1
```

Use:

```text
extra = forbid
```

for canonical protocol models where practical.

Extension data belongs under explicit extension dictionaries.

Do not overconstrain fields where real external systems may legitimately vary.

---

# 75. Character Span Semantics

Unless otherwise documented:

```text
start_char
```

is inclusive.

```text
end_char
```

is exclusive.

Thus:

```text
text[start_char:end_char]
```

selects the referenced span.

Use Unicode string indexing semantics defined by the canonical Python representation unless a future protocol version specifies byte offsets.

---

# 76. Page Number Semantics

Canonical document page numbering should be one-based unless implementation explicitly standardizes otherwise.

Example:

```text
page = 1
```

means the first user-visible document page in the canonical extracted source representation.

PDF-internal numbering and printed page labels may differ and can be stored as metadata.

Once Pydantic models define this convention, they become authoritative.

---

# 77. Ranking Semantics

Retrieval ranks are one-based.

```text
rank = 1
```

means highest-ranked item in that retrieval stage.

Ranks are meaningful only within the stage that produced them.

---

# 78. Metric Re-Scoring

Metric results must reference enough immutable input identity to support:

```text
same TargetObservation
+
new metric version
=
new MetricResult
```

without mutating previous results.

---

# 79. Data-Model Change Policy

Before Pydantic models exist, architectural changes should update this document.

After Pydantic models exist:

1. modify canonical models intentionally;
2. update migrations/protocol as required;
3. update this document only when conceptual semantics changed.

Agents should not repeatedly read this entire document once canonical models are established if the task can be completed from the code.

---

# 80. Source of Truth Transition

Initial phase:

```text
ARCHITECTURE.md
TARGET_PROTOCOL_V1.md
RESILIENCE.md
DATA_MODEL.md
```

define the system.

After the canonical models are implemented:

```text
Pydantic models
```

become authoritative for fields, types, enums, optionality, and validation.

At that point coding-agent instructions should explicitly state:

> Use the canonical Pydantic models as the data-model source of truth. Consult DATA_MODEL.md only for conceptual background when necessary.

This keeps future agent context usage economical.

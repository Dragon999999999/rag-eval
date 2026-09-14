# rag-eval Target Protocol v1

## 1. Purpose

The Target Protocol defines how `rag-eval` communicates with an evaluated system.

The evaluated system is called the **target**.

A target may be:

* a complete RAG system;
* a retriever;
* a reranker pipeline;
* an LLM with supplied context;
* a plain LLM;
* another retrieval/generation system.

`rag-eval` acts as the client/orchestrator.

The protocol is capability-based. Targets do not need to support every operation.

---

# 2. Protocol Version

HTTP base path:

```text
/eval/v1
```

Requests should include:

```http
X-Rag-Eval-Protocol: 1
```

All JSON is UTF-8.

All timestamps use UTC RFC 3339.

Example:

```text
2026-09-14T15:00:01.123456Z
```

IDs should be globally unique.

UUIDv7 or ULID is preferred.

---

# 3. Canonical Transport Model

The protocol defines canonical request and response semantics.

Two initial adapters implement them:

```text
HttpTargetAdapter
PythonTargetAdapter
```

Both must produce the same canonical Pydantic models.

The evaluation engine must not care which transport is used.

---

# 4. Standard HTTP Endpoints

A fully compliant target may expose:

```text
GET    /eval/v1/health
GET    /eval/v1/capabilities
GET    /eval/v1/config-schema

POST   /eval/v1/corpora
GET    /eval/v1/corpora/{corpus_id}
DELETE /eval/v1/corpora/{corpus_id}

POST   /eval/v1/corpora/{corpus_id}/documents
POST   /eval/v1/corpora/{corpus_id}/chunks

GET    /eval/v1/operations/{operation_id}

POST   /eval/v1/retrieve
POST   /eval/v1/query

GET    /eval/v1/requests/{request_id}
```

Only capabilities advertised by the target may be used.

---

# 5. Minimum Target

The smallest useful target only needs to support:

```text
GET  /eval/v1/capabilities
POST /eval/v1/query
```

This is sufficient for plain LLM or simple end-to-end evaluation.

---

# 6. Request Identity

Expensive operations must carry a stable logical identity.

Recommended HTTP headers:

```http
X-Request-ID: <request-id>
Idempotency-Key: <idempotency-key>
```

The request body should also contain `request_id` where applicable.

Definitions:

```text
request_id
    globally unique logical request identifier

idempotency_key
    stable value reused when retrying the same logical operation

request_hash
    evaluator-side hash of canonical request content
```

The evaluator creates these values.

---

# 7. Health

Endpoint:

```http
GET /eval/v1/health
```

Example response:

```json
{
  "status": "READY",
  "target": {
    "name": "example-rag",
    "version": "0.3.0"
  }
}
```

Suggested states:

```text
READY
DEGRADED
NOT_READY
```

Health is operational information and must not be used as benchmark correctness evidence.

---

# 8. Capability Discovery

Endpoint:

```http
GET /eval/v1/capabilities
```

Example:

```json
{
  "protocol_version": "1.0",

  "target": {
    "name": "example-rag",
    "version": "0.3.0",
    "implementation": "custom"
  },

  "capabilities": {
    "query": true,
    "streaming": true,

    "conversation_history": true,

    "retrieval": true,
    "retrieval_stages": true,

    "document_ingestion": true,
    "chunk_ingestion": true,
    "context_injection": true,

    "citations": true,
    "confidence": false,

    "target_trace": true,

    "effective_configuration": true,

    "idempotency": true,
    "request_recovery": true,

    "usage": {
      "tokens": true,
      "cost": false,
      "cpu": false,
      "ram": false,
      "gpu": false,
      "vram": false
    },

    "retrieval_metadata": {
      "rank": true,
      "score": true,
      "document_id": true,
      "chunk_id": true,
      "page": true,
      "character_span": true
    }
  },

  "limits": {
    "max_document_bytes": 104857600,
    "max_chunks_per_request": 1000,
    "max_contexts_per_query": 100,
    "max_concurrent_requests": 16
  },

  "idempotency": {
    "retention_seconds": 604800
  }
}
```

Capabilities may be extended in future protocol revisions.

Unknown optional capability fields should be ignored safely.

---

# 9. Metric Planning

`rag-eval` should inspect target capabilities before executing a benchmark.

Example:

```text
Retrieval Recall@10
    requires retrieval + retrieval metadata + gold evidence

Citation Precision
    requires citations

Confidence Calibration
    requires confidence

GPU utilization
    requires target GPU usage or evaluator-side instrumentation
```

Unsupported metric inputs produce:

```text
UNAVAILABLE_MISSING_INPUT
```

not target failure.

---

# 10. Configuration Schema

Optional endpoint:

```http
GET /eval/v1/config-schema
```

The target may return JSON Schema describing configurable parameters.

Example:

```json
{
  "type": "object",

  "properties": {
    "top_k": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100
    },

    "chunk_size": {
      "type": "integer",
      "minimum": 64
    },

    "embedding_model": {
      "type": "string"
    }
  }
}
```

This allows `rag-eval` to reject invalid experiments before execution.

The protocol must also work when this endpoint is unsupported.

---

# 11. Requested and Effective Configuration

When configuration is supplied by the evaluator, the target may report both:

```json
{
  "configuration": {
    "requested": {
      "top_k": 10
    },

    "effective": {
      "top_k": 8
    }
  }
}
```

Effective configuration is authoritative for describing what the target actually executed.

The requested configuration remains part of the experiment definition.

---

# 12. Corpus Modes

`rag-eval` supports three canonical corpus modes.

```text
DOCUMENTS
CHUNKS
EXTERNAL
```

## DOCUMENTS

The evaluator sends source documents.

The target performs any necessary:

```text
extraction
chunking
embedding
indexing
```

This evaluates the full ingestion pipeline.

## CHUNKS

The evaluator supplies canonical chunks.

The target performs downstream work such as:

```text
embedding
indexing
retrieval
```

This allows controlled chunking experiments.

## EXTERNAL

The target already owns a prepared corpus.

No ingestion is required.

---

# 13. Create Corpus

Endpoint:

```http
POST /eval/v1/corpora
```

Example request:

```json
{
  "request_id": "01K...",

  "name": "benchmark-corpus",

  "mode": "DOCUMENTS",

  "parameters": {
    "embedding_model": "bge-m3",
    "chunk_size": 512,
    "chunk_overlap": 64
  },

  "metadata": {
    "run_id": "run-001"
  }
}
```

Example response:

```json
{
  "corpus_id": "corpus-001",

  "status": "EMPTY",

  "configuration": {
    "requested": {
      "chunk_size": 512
    },

    "effective": {
      "chunk_size": 512
    }
  }
}
```

---

# 14. Corpus State

Endpoint:

```http
GET /eval/v1/corpora/{corpus_id}
```

Suggested states:

```text
EMPTY
BUILDING
READY
FAILED
DELETING
DELETED
```

Queries requiring a corpus should normally execute only against `READY`.

---

# 15. Delete Corpus

Endpoint:

```http
DELETE /eval/v1/corpora/{corpus_id}
```

Deleting an evaluation corpus must not affect unrelated target data.

Targets should isolate evaluation corpora where possible.

---

# 16. Document Upload

Endpoint:

```http
POST /eval/v1/corpora/{corpus_id}/documents
Content-Type: multipart/form-data
```

Parts:

```text
file
metadata
```

Example metadata:

```json
{
  "request_id": "01K...",

  "document_id": "paper-17",

  "filename": "paper17.pdf",

  "mime_type": "application/pdf",

  "sha256": "abc123...",

  "metadata": {
    "title": "Example Paper",
    "year": 2026
  }
}
```

The supplied `document_id` is the evaluator's stable identity for the source.

Targets should preserve it through retrieval and citations whenever possible.

If a SHA-256 is supplied, the target should verify it when feasible.

---

# 17. Asynchronous Ingestion

Document ingestion may be asynchronous.

Example response:

```json
{
  "operation_id": "operation-17",
  "status": "PENDING"
}
```

The evaluator polls:

```http
GET /eval/v1/operations/operation-17
```

Example:

```json
{
  "operation_id": "operation-17",

  "kind": "DOCUMENT_INGESTION",

  "status": "RUNNING",

  "progress": {
    "value": 0.61,
    "stage": "embedding"
  }
}
```

Final:

```json
{
  "operation_id": "operation-17",

  "status": "SUCCEEDED",

  "result": {
    "document_id": "paper-17",
    "pages_processed": 18,
    "chunks_created": 132
  }
}
```

---

# 18. Operation States

Canonical operation states:

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

An operation failure should include the canonical error envelope.

---

# 19. Chunk Upload

Endpoint:

```http
POST /eval/v1/corpora/{corpus_id}/chunks
```

Example:

```json
{
  "request_id": "01K...",

  "chunks": [
    {
      "chunk_id": "paper17-c001",

      "document_id": "paper-17",

      "text": "Example chunk content.",

      "location": {
        "page": 3,
        "start_char": 920,
        "end_char": 1391
      },

      "metadata": {}
    }
  ]
}
```

For large chunk sets, targets may support:

```text
Content-Type: application/x-ndjson
```

Each line contains one canonical chunk.

The evaluator should batch uploads according to advertised limits.

---

# 20. Source Location

The canonical source-location concept may contain:

```text
document_id
chunk_id
page
start_char
end_char
section
metadata
```

`document_id` is the primary stable identity.

Fields may be absent when unavailable.

Do not fabricate unavailable source coordinates.

---

# 21. Independent Retrieval

Endpoint:

```http
POST /eval/v1/retrieve
```

This endpoint performs retrieval without answer generation.

Example request:

```json
{
  "request_id": "01K...",

  "corpus_id": "corpus-001",

  "query": "What limitation do the authors identify?",

  "history": [],

  "parameters": {
    "top_k": 10
  },

  "filters": {},

  "include": {
    "stages": true,
    "trace": true,
    "usage": true,
    "effective_configuration": true
  }
}
```

This endpoint is important for inexpensive retriever-only experiments.

---

# 22. Retrieval Stages

Retrieval must support zero or more stages.

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

Canonical stage types should include:

```text
CANDIDATE_RETRIEVAL
FUSION
RERANK
FILTER
COMPRESSION
FINAL_CONTEXT
CUSTOM
```

Each stage contains an ordered collection of retrieved items.

---

# 23. Retrieval Response

Example:

```json
{
  "request_id": "01K...",

  "retrieval": {
    "stages": [
      {
        "stage_id": "dense",

        "type": "CANDIDATE_RETRIEVAL",

        "items": []
      },

      {
        "stage_id": "reranked",

        "parent_stage_id": "dense",

        "type": "RERANK",

        "items": []
      },

      {
        "stage_id": "final",

        "parent_stage_id": "reranked",

        "type": "FINAL_CONTEXT",

        "items": []
      }
    ]
  },

  "trace": {
    "spans": []
  },

  "usage": {},

  "configuration": {
    "requested": {},
    "effective": {}
  }
}
```

---

# 24. Retrieved Item

Canonical example:

```json
{
  "retrieval_id": "r-283",

  "rank": 1,

  "text": "The main limitation is ...",

  "source": {
    "document_id": "paper-17",
    "chunk_id": "paper17-c023",
    "page": 8,
    "start_char": 1404,
    "end_char": 1694
  },

  "score": {
    "value": 0.927,
    "type": "cosine_similarity"
  },

  "metadata": {}
}
```

Retrieval scores must include score semantics whenever known.

Common score types:

```text
cosine_similarity
dot_product
euclidean_distance
bm25
rrf
cross_encoder
probability
custom
```

---

# 25. Final Context

The `FINAL_CONTEXT` stage identifies the context actually supplied to the generation model.

Example:

```text
50 candidates retrieved
20 reranked
5 supplied to LLM
```

Only the final 5 belong to `FINAL_CONTEXT`.

Groundedness metrics normally evaluate against this stage.

Retriever metrics may evaluate earlier stages.

---

# 26. Query Endpoint

Endpoint:

```http
POST /eval/v1/query
```

Canonical request:

```json
{
  "request_id": "01K...",

  "corpus_id": "corpus-001",

  "query": "What limitation do the authors identify?",

  "history": [],

  "context_policy": "TARGET_RETRIEVAL",

  "supplied_contexts": null,

  "parameters": {
    "top_k": 10
  },

  "include": {
    "retrieval": true,
    "citations": true,
    "confidence": true,
    "trace": true,
    "usage": true,
    "effective_configuration": true
  },

  "stream": false
}
```

---

# 27. Context Policies

Canonical values:

```text
TARGET_RETRIEVAL
SUPPLIED_CONTEXT
NO_CONTEXT
```

## TARGET_RETRIEVAL

Normal RAG execution:

```text
query
  |
target retrieval
  |
generation
```

## SUPPLIED_CONTEXT

The evaluator directly supplies evidence:

```text
query + contexts
       |
       v
     target
```

This mode is useful for groundedness and hallucination evaluation.

## NO_CONTEXT

The target receives no retrieval context.

Useful for plain LLM evaluation.

---

# 28. Supplied Context

Example:

```json
{
  "context_id": "ctx-001",

  "text": "Evidence text...",

  "source": {
    "document_id": "paper-17",
    "page": 8,
    "start_char": 1404,
    "end_char": 1694
  },

  "metadata": {}
}
```

Targets should preserve source information when generating citations if supported.

---

# 29. Conversation History

History is a sequence of messages.

Canonical roles should include at least:

```text
system
user
assistant
tool
```

Example:

```json
[
  {
    "role": "user",
    "content": "What method does the paper propose?"
  },

  {
    "role": "assistant",
    "content": "It proposes ..."
  }
]
```

Targets not supporting history must advertise that limitation.

---

# 30. Query Response

Example:

```json
{
  "protocol_version": "1.0",

  "request_id": "01K...",

  "status": "COMPLETED",

  "answer": {
    "text": "The authors identify ...",

    "finish_reason": "STOP",

    "citations": []
  },

  "retrieval": {
    "stages": []
  },

  "confidence": [],

  "trace": {
    "spans": []
  },

  "usage": {},

  "configuration": {
    "requested": {},
    "effective": {}
  },

  "warnings": []
}
```

Optional sections may be omitted or null according to the canonical models.

---

# 31. Finish Reason

Canonical finish reasons:

```text
STOP
LENGTH
REFUSAL
CONTENT_FILTER
ERROR
CANCELLED
UNKNOWN
```

A legitimate model refusal is a successful protocol execution.

Example:

```json
{
  "answer": {
    "text": "I cannot answer this request.",
    "finish_reason": "REFUSAL"
  }
}
```

Do not convert such responses into transport errors.

---

# 32. Citations

A citation should identify:

```text
where in the answer it applies
+
what source evidence it references
```

Example:

```json
{
  "citation_id": "citation-1",

  "answer_span": {
    "start_char": 0,
    "end_char": 72
  },

  "source": {
    "document_id": "paper-17",
    "chunk_id": "paper17-c023",
    "retrieval_id": "r-283",
    "page": 8,
    "start_char": 1404,
    "end_char": 1694
  },

  "display": "[1]",

  "metadata": {}
}
```

Fields unavailable to the target may be omitted.

Citation strings alone should not be treated as sufficient provenance when structured information exists.

---

# 33. Confidence

Targets may return zero or more confidence signals.

Example:

```json
[
  {
    "name": "answer_confidence",

    "value": 0.87,

    "range": {
      "min": 0.0,
      "max": 1.0
    },

    "semantics": "probability_of_correctness"
  }
]
```

Possible semantics include:

```text
probability_of_correctness
probability_of_support
retrieval_confidence
model_specific
custom
```

Do not assume all confidence values are probabilities unless explicitly declared.

---

# 34. Trace

Target tracing uses hierarchical spans.

Example:

```json
{
  "trace_id": "trace-772",

  "spans": [
    {
      "span_id": "s1",
      "parent_span_id": null,

      "name": "query",

      "started_at": "2026-09-14T15:00:00.000Z",

      "duration_ms": 1482.7,

      "attributes": {}
    },

    {
      "span_id": "s2",
      "parent_span_id": "s1",

      "name": "retrieval",

      "started_at": "2026-09-14T15:00:00.020Z",

      "duration_ms": 84.2,

      "attributes": {}
    }
  ]
}
```

Recommended span names:

```text
embedding
retrieval
dense_retrieval
lexical_retrieval
fusion
reranking
context_building
prompt_building
llm_queue
llm_prefill
generation
citation_generation
postprocessing
```

Custom span names are valid.

---

# 35. Client vs Target Trace

`rag-eval` records client-observed timings independently.

Target-reported timing must not replace client measurements.

Example:

```text
client total HTTP time
client TTFT
client token arrival times

target retrieval duration
target reranker duration
target generation duration
```

All are useful and must remain distinguishable.

---

# 36. Usage

Canonical usage may contain:

```json
{
  "tokens": {
    "input": 4821,
    "output": 319,
    "total": 5140,
    "retrieved_context": 3710
  },

  "calls": {
    "llm": 1,
    "embedding": 1,
    "retrieval": 1,
    "reranker": 1
  },

  "cost": {
    "value": 0.0137,
    "currency": "USD"
  },

  "resources": {
    "cpu_time_ms": null,
    "cpu_peak_percent": null,
    "ram_peak_bytes": null,

    "gpu_time_ms": null,
    "gpu_peak_percent": null,
    "vram_peak_bytes": null
  }
}
```

All resource values are optional unless explicitly advertised.

---

# 37. Raw Prompt Exposure

Targets may optionally expose generation prompt information.

This is not required because prompts may contain sensitive implementation details.

A capability such as:

```text
raw_prompt = true
```

may advertise availability.

More important than raw prompts is identifying which contexts reached generation.

---

# 38. Streaming

Targets advertising streaming should support:

```http
Accept: text/event-stream
```

for:

```http
POST /eval/v1/query
```

when:

```json
{
  "stream": true
}
```

SSE is the canonical HTTP streaming transport for v1.

---

# 39. Streaming Event Envelope

Example:

```json
{
  "event_id": "event-17",

  "request_id": "01K...",

  "sequence": 17,

  "type": "token.delta",

  "timestamp": "2026-09-14T15:00:01.343Z",

  "data": {}
}
```

Sequence numbers must increase monotonically within a stream.

---

# 40. Canonical Streaming Events

Recommended event types:

```text
request.started

retrieval.started
retrieval.stage.completed
retrieval.completed

generation.started

token.delta

citation.created
confidence.updated
usage.updated

generation.completed

request.completed

warning
error
```

Example token event:

```json
{
  "type": "token.delta",

  "data": {
    "text": "limitation"
  }
}
```

---

# 41. Streaming Completion

The final:

```text
request.completed
```

event must provide or reference the complete canonical query result.

Streaming and non-streaming requests must normalize into the same `QueryResponse`.

---

# 42. Partial Streams

If streaming terminates unexpectedly, already received events remain valid observations.

The evaluator may classify the answer as:

```text
partial
truncated
failed
```

depending on available information.

Targets and adapters must not discard already received output.

---

# 43. Error Response

Non-success protocol responses use a canonical error envelope.

Example:

```json
{
  "request_id": "01K...",

  "error": {
    "error_id": "error-42",

    "code": "RATE_LIMITED",

    "category": "RATE_LIMIT",

    "message": "Provider rate limit exceeded.",

    "stage": "generation",

    "retryable": true,

    "retry_after_ms": 30000,

    "provider": {
      "name": "example-provider",
      "status": 429,
      "code": "rate_limit_exceeded"
    },

    "details": {}
  }
}
```

---

# 44. Error Categories

Canonical v1 categories:

```text
VALIDATION
UNSUPPORTED_CAPABILITY

AUTHENTICATION
AUTHORIZATION

NOT_FOUND
CONFLICT

NETWORK
CONNECTION
TIMEOUT
RATE_LIMIT

RESOURCE_EXHAUSTED

INGESTION
RETRIEVAL
GENERATION

INVALID_RESPONSE

INTERNAL
UNKNOWN
```

Adapters should normalize native errors into these categories when possible.

---

# 45. HTTP Status Guidance

Recommended mapping:

```text
400   validation / malformed request
401   authentication
403   authorization
404   resource not found
409   state or idempotency conflict
413   payload too large
415   unsupported media type
422   semantically invalid configuration
429   rate limit

500   target internal error
502   invalid downstream/provider response
503   temporarily unavailable
504   timeout
```

The structured `retryable` value is more important than HTTP status alone.

---

# 46. Idempotency

Targets advertising idempotency must guarantee:

```text
same idempotency key
+
same logical request
=
same logical operation
```

A repeated request must not cause duplicate expensive execution if the original operation already completed.

Targets may return:

```http
Idempotency-Replayed: true
```

on replay.

---

# 47. Idempotency Conflict

If:

```text
same idempotency key
+
different logical request
```

the target should return:

```text
HTTP 409
```

with:

```text
IDEMPOTENCY_CONFLICT
```

The evaluator must not silently create a new operation using the conflicting key.

---

# 48. Request Recovery

Targets advertising request recovery expose:

```http
GET /eval/v1/requests/{request_id}
```

Possible response states:

```text
PENDING
RUNNING
COMPLETED
FAILED
CANCELLED
NOT_FOUND
```

If completed, the response should include or reference the canonical result.

This endpoint exists primarily to recover uncertain network/process failures.

---

# 49. Python Adapter Contract

The Python adapter mirrors the same logical operations.

Conceptually:

```python
class TargetAdapter(Protocol):

    async def capabilities(self) -> TargetCapabilities:
        ...

    async def health(self) -> HealthStatus:
        ...

    async def create_corpus(
        self,
        request: CreateCorpusRequest,
    ) -> CreateCorpusResponse:
        ...

    async def delete_corpus(
        self,
        corpus_id: str,
    ) -> None:
        ...

    async def upload_document(
        self,
        corpus_id: str,
        document: DocumentUpload,
    ) -> Operation:
        ...

    async def upload_chunks(
        self,
        corpus_id: str,
        chunks: AsyncIterator[Chunk],
    ) -> Operation:
        ...

    async def get_operation(
        self,
        operation_id: str,
    ) -> Operation:
        ...

    async def retrieve(
        self,
        request: RetrieveRequest,
    ) -> RetrieveResponse:
        ...

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        ...

    async def stream_query(
        self,
        request: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
        ...

    async def recover_request(
        self,
        request_id: str,
    ) -> RequestRecoveryResult:
        ...
```

Exact signatures are defined by the implemented Pydantic models and Python protocol.

---

# 50. Unsupported Operations

A target that does not support an operation should produce a normalized:

```text
UNSUPPORTED_CAPABILITY
```

response/error.

Do not rely on:

```text
NotImplementedError
500 Internal Server Error
missing method crashes
```

for normal capability negotiation.

---

# 51. Raw Response Preservation

The HTTP adapter must preserve the raw target response before downstream normalization whenever possible.

The Python adapter should likewise retain a serializable representation of returned target data when configured.

Normalization failure must not require repeating successful target execution.

See `RESILIENCE.md`.

---

# 52. Protocol Extensibility

Target-specific extensions belong in explicit:

```text
metadata
attributes
details
```

objects.

Avoid adding undocumented top-level fields for project-specific behavior.

Protocol extensions must not change the meaning of existing fields.

---

# 53. Security

Authentication is transport/configuration specific.

Examples:

```text
Bearer token
API key header
mTLS
no authentication
```

Secrets must not be embedded into benchmark YAML that is intended for version control.

Use environment-variable or secret-store references.

The target should isolate evaluation corpora and avoid exposing unrelated/private data.

---

# 54. Protocol Compliance Levels

Useful conceptual profiles:

```text
LLM-basic
    query

LLM-grounding
    query + supplied context

RAG-basic
    query + retrieval observation

RAG-retriever
    independent retrieval

RAG-full
    ingestion + retrieval + query

RAG-observable
    full + traces + usage + citations

RAG-resilient
    observable + idempotency + request recovery
```

These are descriptive profiles, not required transport fields.

---

# 55. v1 Compatibility Rule

Minor additions may extend v1 without breaking existing clients if:

* existing field meanings remain unchanged;
* newly introduced fields are optional;
* unknown optional fields can be ignored safely.

Breaking semantic changes require a new protocol version.

---

# 56. Implementation Priority

Initial required implementation:

```text
capabilities
health
query
retrieve

document ingestion
chunk ingestion

canonical errors

request identity
idempotency support in adapter semantics
request recovery hooks
```

Streaming, detailed trace/resource usage, and generic REST mapping may follow, but their data structures should be anticipated by the initial canonical models.

---

# 57. Source of Truth

Before canonical Pydantic models exist, this document defines Target Protocol v1.

After they are implemented:

```text
Pydantic protocol models
```

are the executable source of truth.

This document remains the semantic explanation of the protocol.

If this document and the implemented protocol differ unintentionally, correct the inconsistency.

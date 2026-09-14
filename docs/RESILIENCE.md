# rag-eval Resilience and Recovery

## 1. Purpose

Evaluation runs may be expensive, long-running, and dependent on unreliable external systems.

Failures may include:

* LLM/API throttling;
* HTTP 429 responses;
* provider outages;
* network failures;
* connection resets;
* request timeouts;
* target crashes;
* evaluator crashes;
* machine restarts;
* parsing bugs;
* metric bugs;
* object-storage failures;
* database failures.

The main resilience objective is:

> Never repeat expensive successful work when the result can be recovered or reused.

A run containing thousands of queries must be resumable with minimal duplicated work.

---

# 2. Fundamental Persistence Rule

Persist state **before** beginning an expensive operation.

Persist the raw result **immediately after** receiving it.

The normal ordering is:

```text
1. construct canonical request
2. assign request_id
3. assign idempotency_key
4. hash request
5. persist attempt as RUNNING
6. commit database transaction

7. execute target request

8. persist raw response artifact
9. persist artifact metadata/hash
10. commit

11. normalize raw response
12. persist TargetObservation
13. mark TARGET_COMPLETE
14. commit

15. calculate metrics
16. persist metric results
17. mark COMPLETE
```

Do not delay persistence until an entire benchmark or batch finishes.

---

# 3. Execution Hierarchy

Use:

```text
Run
└── CaseExecution
    └── Attempt
        └── optional StageExecution
```

## Run

Represents one immutable experiment configuration against one benchmark configuration.

## CaseExecution

Represents one logical benchmark case in one run.

## Attempt

Represents one attempt to execute an expensive target operation.

Attempts are append-only.

Never overwrite a failed or uncertain attempt.

## StageExecution

Optional detailed record for sub-stages such as:

```text
corpus upload
retrieval
generation
judge call
metric computation
```

---

# 4. Case Execution States

Canonical case-level states:

```text
PENDING
RUNNING
TARGET_COMPLETE
SCORING
COMPLETE

RETRY_PENDING
FAILED
UNKNOWN
```

Meaning:

## PENDING

The case has not yet been sent to the target.

## RUNNING

A target request has been durably registered and may be executing.

## TARGET_COMPLETE

A usable target response or TargetObservation has been durably persisted.

The target must not be queried again for normal scoring.

## SCORING

Metric evaluation is in progress.

## COMPLETE

Target execution and required scoring are complete.

## RETRY_PENDING

The latest target attempt failed with a retryable error.

## FAILED

A permanent error or exhausted retry policy prevents completion.

## UNKNOWN

The evaluator cannot determine whether an expensive target operation completed.

This normally occurs after communication/process failure against a target without sufficient idempotency/recovery support.

---

# 5. Attempt States

Attempts should distinguish at least:

```text
CREATED
RUNNING
RESPONSE_RECEIVED
NORMALIZED
SUCCEEDED

RETRYABLE_FAILURE
PERMANENT_FAILURE
UNKNOWN_OUTCOME
```

`RESPONSE_RECEIVED` is significant.

Once a raw target response has been durably stored, later parsing/scoring failures must not cause the target to be queried again.

---

# 6. Request Identity

Every logical target request receives:

```text
request_id
idempotency_key
canonical_request_hash
```

Recommended relationship:

```text
request_id:
    globally unique identifier

idempotency_key:
    stable identifier reused across retries
    of the same logical operation

canonical_request_hash:
    SHA-256 of canonical logical request payload
```

A retry must reuse the same idempotency key only if it is semantically the same operation.

---

# 7. Idempotency Contract

Targets advertising idempotency support must guarantee:

```text
same idempotency key
+
same request payload/hash
=
same logical operation/result
```

A repeated request must not execute another expensive generation if the original operation already succeeded.

If the same idempotency key is supplied with a different logical request:

```text
409 Conflict
IDEMPOTENCY_CONFLICT
```

should be returned.

Targets may expose an idempotency retention period.

The evaluator must not assume indefinite retention.

---

# 8. Request Recovery

Targets may expose:

```text
recover_request(request_id)
```

or HTTP equivalent:

```text
GET /eval/v1/requests/{request_id}
```

Possible target states:

```text
PENDING
RUNNING
COMPLETED
FAILED
CANCELLED
NOT_FOUND
```

If `COMPLETED`, the evaluator should retrieve/reuse the existing response.

Do not issue a second expensive request.

---

# 9. Unknown Outcome Problem

Important failure case:

```text
evaluator sends request
        |
        v
target executes successfully
        |
        X
network/evaluator crashes before response is persisted
```

The evaluator cannot safely assume failure.

Recovery order:

```text
1. query target by request_id if request recovery exists

2. otherwise replay same idempotency key if idempotency exists

3. otherwise mark previous attempt UNKNOWN_OUTCOME

4. create a new attempt only if policy permits re-execution
```

Never silently treat an unknown result as a normal failed attempt.

---

# 10. Resume Algorithm

When:

```bash
rag-eval resume RUN_ID
```

is executed, inspect persisted case state.

Use approximately:

```text
COMPLETE
    -> skip

TARGET_COMPLETE
    -> score/re-score only

SCORING
    -> determine whether scoring state is stale
    -> restart scoring if necessary

RETRY_PENDING
    -> retry according to retry policy

PENDING
    -> execute normally

RUNNING
    -> determine whether execution is stale
    -> recover request if possible

FAILED
    -> skip unless explicit retry/reset requested

UNKNOWN
    -> attempt request recovery/idempotent replay
```

Never restart the whole benchmark because one case failed.

---

# 11. Stale RUNNING Detection

An evaluator may crash while an attempt remains `RUNNING`.

Store:

```text
started_at
heartbeat_at where applicable
timeout/deadline
worker identity where applicable
```

On resume, if a `RUNNING` operation is clearly stale:

```text
recover via request_id
```

if supported.

Otherwise:

```text
mark attempt UNKNOWN_OUTCOME
```

and apply the configured recovery policy.

---

# 12. Retry Classification

Errors must be normalized into categories.

At minimum:

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

Each `ErrorRecord` should contain:

```text
category
error code
message
stage
retryable
HTTP status if applicable
provider status/code if applicable
retry_after if applicable
timestamp
raw error artifact if needed
```

---

# 13. Retryable Failures

Normally retryable:

```text
network interruption
connection reset
temporary DNS failure

HTTP 408
HTTP 429
HTTP 500
HTTP 502
HTTP 503
HTTP 504

temporary provider unavailable
temporary resource exhaustion
```

Whether a specific error is retryable should remain explicit in the normalized error.

Do not blindly retry all 5xx/4xx indefinitely.

---

# 14. Non-Retryable Failures

Normally non-retryable:

```text
invalid benchmark request
unsupported capability
bad authentication
forbidden operation
invalid configuration
permanent parsing/schema incompatibility
payload fundamentally too large
missing required corpus
```

These should fail promptly instead of consuming retry budget.

---

# 15. Rate Limiting

HTTP/provider rate limiting must not immediately fail a case.

For:

```text
429 Too Many Requests
```

the evaluator should:

1. record the failed attempt;
2. read `Retry-After` where available;
3. temporarily reduce/pause new traffic;
4. retry according to policy.

Rate limiting contributes to reliability metrics.

It is not equivalent to an incorrect target answer.

---

# 16. Backoff

Default retry behavior should use exponential backoff with jitter.

Configuration should allow:

```text
maximum attempts
initial delay
maximum delay
retryable status codes
retryable error categories
```

Example conceptual sequence:

```text
1s
2s
4s
8s
...
```

plus randomized jitter.

`Retry-After` should take precedence when valid and larger than the computed delay where appropriate.

---

# 17. Circuit Breaker

Repeated infrastructure failures should stop the evaluator from flooding an unhealthy target.

Example:

```text
consecutive 429 / timeout / 503
          |
          v
open circuit
          |
          v
pause new expensive requests
          |
          v
health/probe request
          |
          v
recover -> resume
```

The circuit breaker operates at target/provider scope, not as a permanent case failure.

Exact thresholds should be configurable.

---

# 18. Bounded Concurrency

All benchmark concurrency must be bounded.

Configuration may include:

```text
max concurrency
max requests/sec
provider-specific concurrency
```

The execution engine must not create an unbounded task for every benchmark case.

Use worker/task queues or bounded async semaphores.

---

# 19. Graceful Shutdown

On:

```text
SIGINT
SIGTERM
normal cancellation
```

the evaluator should:

1. stop scheduling new cases;
2. allow a short configurable window for active persistence;
3. preserve active attempts;
4. flush artifact metadata where possible;
5. close database/object-store clients cleanly.

Do not mark unfinished expensive operations as successful.

---

# 20. Raw Response First

After a successful network response:

```text
raw response
    |
    v
artifact storage
    |
    v
database artifact pointer
    |
    v
normalization
```

Never normalize first and store later.

Reason:

```text
expensive LLM call succeeds
        |
parser crashes
        |
raw response already preserved
        |
parser can be fixed and rerun
```

---

# 21. Normalization Failure

If raw target data exists but normalization fails:

```text
attempt = RESPONSE_RECEIVED
case = TARGET_RESPONSE_AVAILABLE / normalization failure
```

Do not call the target again.

Resume should reload the artifact and rerun normalization.

The exact database representation may differ, but the semantic invariant must hold.

---

# 22. Metric Failure

If target execution succeeds but one metric crashes:

```text
TargetObservation remains valid
```

Only the affected metric should become:

```text
FAILED
```

or be retried.

Do not invalidate the target execution.

Do not rerun the target.

---

# 23. Judge Failure

Model-based evaluation calls are themselves expensive and unreliable.

Judge calls should use similar resilience concepts:

```text
judge request ID
attempts
raw judge response
retry behavior
judge error state
```

A failed semantic metric judge must not trigger rerunning the evaluated RAG.

---

# 24. Streaming Persistence

Streaming target calls may be interrupted after producing substantial output.

Where configured, persist streaming events incrementally.

Event records should include:

```text
request_id
sequence
event type
client receive timestamp
payload
```

This supports:

```text
TTFT
inter-token latency
partial-response diagnosis
truncated-response classification
```

A partially persisted stream may be useful even if the request ultimately fails.

---

# 25. Streaming Completion

The final successful streaming event should contain or map to the same canonical `QueryResponse` used by non-streaming requests.

Streaming is a transport mechanism, not a separate result model.

---

# 26. Partial Responses

If generation ends unexpectedly:

```text
answer may be partial
finish_reason = ERROR/LENGTH/etc.
```

Retain the partial text.

Do not discard it.

Metrics may classify it as incomplete or unavailable depending on their requirements.

---

# 27. Model Refusals

A legitimate model refusal is not necessarily a transport failure.

Example:

```text
"I cannot answer this request."
```

If the target successfully produced that response:

```text
HTTP success
answer persisted
finish_reason = REFUSAL
```

Evaluation can then calculate refusal/abstention metrics.

Do not convert all refusals into `ERR`.

---

# 28. Database Transaction Boundaries

Keep database transactions short.

Do not hold an open PostgreSQL transaction while:

```text
waiting on an LLM
uploading a large PDF
waiting minutes for indexing
polling external services
```

Typical pattern:

```text
transaction:
    create/update operation state
commit

external operation

transaction:
    persist resulting state
commit
```

---

# 29. Artifact Durability

Large artifacts should be immutable once finalized.

For every stored artifact, retain:

```text
SHA-256
size
content type
URI/key
timestamp
```

If upload fails:

```text
do not mark the associated result durable
```

Use atomic local writes where applicable.

For S3-compatible storage, write complete objects before committing the durable artifact pointer to PostgreSQL.

---

# 30. Database / Object Storage Consistency

PostgreSQL is the authoritative index of run state.

Object storage is authoritative for artifact bytes.

A response is considered durably captured only when:

```text
artifact successfully stored
+
artifact pointer/hash committed to PostgreSQL
```

If object upload succeeds but the database transaction fails, orphan cleanup may occur later.

Never claim the target response is durable before the DB reference is committed.

---

# 31. Duplicate Execution Prevention

Before creating a new target attempt, inspect case state.

Never execute target calls for:

```text
COMPLETE
TARGET_COMPLETE
```

unless explicitly requested as a new run.

Use database uniqueness constraints/locking where necessary to prevent two workers from executing the same logical case simultaneously.

---

# 32. Multi-Worker Safety

The architecture should remain compatible with future distributed workers.

Case claiming should use transactional locking or equivalent mechanisms.

For PostgreSQL, appropriate mechanisms may include:

```text
SELECT ... FOR UPDATE SKIP LOCKED
```

or equivalent queue semantics.

Do not require distributed execution initially, but avoid designs that make it impossible.

---

# 33. Run Cancellation

Cancellation should distinguish:

```text
user cancelled run
target failed
benchmark completed
```

On cancellation:

```text
pending cases -> CANCELLED/SKIPPED as appropriate
running operations -> preserve current attempts
completed target results -> retain
```

Previously completed work must remain reusable.

---

# 34. Retry Budget

Retries should be tracked explicitly.

Useful fields:

```text
attempt_number
max_attempts
retry reason
delay
next_retry_at
```

Do not implement recursive retry functions that lose attempt history.

Each attempt must remain observable.

---

# 35. Error Preservation

Preserve sufficient error detail for later analysis:

```text
normalized error category
normalized error code

human-readable message

exception class where local
HTTP status
provider code

stage
retryability

raw response/error artifact where appropriate
```

Avoid placing secrets in error artifacts or logs.

---

# 36. Failure Metrics

The system should support deriving:

```text
request success rate
failure rate

first-attempt success rate
retry success rate
retry exhaustion rate

timeout rate
rate-limit rate
connection failure rate

malformed-response rate

partial completion rate

average attempts/query

resume efficiency

duplicate execution rate

unknown-outcome rate
```

Failure information therefore must remain structured rather than only appearing in logs.

---

# 37. Resume Efficiency

A key operational metric is:

```text
already completed expensive operations
not repeated after restart
```

A correct resume should normally rerun only:

* unfinished operations;
* explicitly retryable failures;
* uncertain operations that cannot be recovered otherwise.

---

# 38. Scoring Is Independently Resumable

Target execution and scoring are separate phases logically even if executed consecutively.

Example state:

```text
TARGET_COMPLETE
```

means:

> The expensive system-under-test output is safely captured.

If the evaluator crashes after this point:

```text
resume -> scoring only
```

This boundary is essential.

---

# 39. Re-Scoring

The following must be possible:

```bash
rag-eval score RUN_ID
```

after:

```text
new metric implementation
fixed metric bug
new judge
new rubric
new report
```

without executing the evaluated target again.

Metric versions must be recorded.

---

# 40. Immutable Historical Attempts

Never update an earlier attempt to make history look successful.

Example:

```text
attempt 1 -> HTTP 429
attempt 2 -> timeout
attempt 3 -> success
```

Persist all three.

The case can ultimately be `COMPLETE`.

Reliability metrics still see:

```text
3 attempts
1 rate limit
1 timeout
```

---

# 41. Retry vs New Run

A retry means:

```text
same logical benchmark case
same run/configuration
same logical request
```

A new configuration means a new run.

Do not use retries to silently alter:

```text
model
top_k
prompt
chunk size
temperature
```

Such changes invalidate direct equivalence and require a new run/configuration identity.

---

# 42. Configuration Consistency on Resume

A resumed run must use the persisted run configuration.

Do not silently replace it with a modified YAML file.

If the supplied configuration differs from the persisted run hash:

```text
reject
```

or require explicit creation of a new run.

---

# 43. Corpus Consistency

Documents and benchmark inputs should be identified by content hashes.

On resume or another machine, verify expected hashes where appropriate.

Do not silently evaluate against a changed PDF that happens to use the same filename.

---

# 44. Safe Process Restarts

A normal restart sequence should be:

```text
start evaluator
    |
load persisted run
    |
discover stale state
    |
recover target operations
    |
resume pending/retryable work
    |
score preserved observations
    |
continue
```

The evaluator should not require restoring Python in-memory objects.

All essential state must be reconstructable from durable storage.

---

# 45. No In-Memory-Only Critical State

The following must never exist only in process memory if losing them would force expensive recomputation:

```text
run identity
case execution state
attempt identity
request ID
idempotency key
request hash
raw response reference
TargetObservation status
```

Caches may remain ephemeral.

Critical execution state may not.

---

# 46. Example Recovery Scenario: Rate Limit

```text
case 512
  |
attempt 1
  |
HTTP 429
  |
persist RATE_LIMIT
  |
read Retry-After
  |
RETRY_PENDING
  |
circuit breaker may pause target
  |
attempt 2
  |
success
  |
persist raw response
  |
TARGET_COMPLETE
  |
score
  |
COMPLETE
```

Both attempts remain stored.

---

# 47. Example Recovery Scenario: Parser Crash

```text
target succeeds
  |
raw response stored
  |
parser crashes
  |
process exits
```

After restart:

```text
raw response exists
  |
rerun parser
  |
create TargetObservation
  |
score
```

No target request is repeated.

---

# 48. Example Recovery Scenario: Connection Lost After Generation

```text
request sent
  |
target generates answer
  |
connection lost
  |
client has no response
```

Resume:

```text
recover_request(request_id)
```

If:

```text
COMPLETED
```

fetch/reuse existing response.

Otherwise use the same idempotency key where supported.

Only if neither recovery nor idempotency exists should another attempt risk repeating the work.

---

# 49. Example Recovery Scenario: Evaluator Crash at Case 4382

Database state:

```text
1-4381      COMPLETE

4382        TARGET_COMPLETE

4383        RUNNING

4384-10000  PENDING
```

Resume behavior:

```text
1-4381
    skip

4382
    score persisted observation

4383
    recover request or idempotently replay

4384+
    continue normal execution
```

Never restart cases `1-4381`.

---

# 50. Resilience Definition of Done

The resilience layer is considered minimally complete when automated tests prove:

```text
HTTP 429
-> retry
-> successful continuation

timeout
-> persisted failed attempt
-> retry

target 500
-> backoff
-> retry according to policy

process interruption after raw response persistence
-> resume
-> target not called again

process interruption after target execution but before client confirmation
-> request recovery/idempotency used

metric crash
-> TargetObservation preserved
-> re-score succeeds

full evaluator restart
-> completed cases skipped
-> unfinished cases continue
```

The central invariant is:

> Once expensive target output is durably captured, no downstream failure should require regenerating that output.

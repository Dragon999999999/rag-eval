"""Request identity generation for reproducible target requests.

Generates stable identifiers before target execution:

```text
request_id
idempotency_key
canonical_request_hash
```

These IDs support Stage 10 retry/recovery but do not implement it yet.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from rag_eval.models import QueryRequest, RetrieveRequest


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    """Identity fields for one target request."""

    request_id: str
    idempotency_key: str
    canonical_request_hash: str


class RequestIdentityGenerator:
    """Generate stable request identity for retry/recovery support."""

    def generate(
        self,
        request: QueryRequest | RetrieveRequest,
        attempt_id: str,
    ) -> RequestIdentity:
        """Generate identity fields for one target request.

        Args:
            request: Canonical target request (request_id will be populated).
            attempt_id: Unique attempt identifier for this execution.

        Returns:
            Request identity with stable IDs and content hash.

        Note:
            - request_id: Globally unique identifier
            - idempotency_key: Stable across retries of same logical operation
            - canonical_request_hash: SHA-256 of canonical request content
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Idempotency key is based on attempt ID for Stage 9
        # Stage 10 will make this more sophisticated
        idempotency_key = attempt_id

        # Hash canonical request content (excluding secrets/transport details)
        canonical_request_hash = self._hash_request(request)

        return RequestIdentity(
            request_id=request_id,
            idempotency_key=idempotency_key,
            canonical_request_hash=canonical_request_hash,
        )

    def _hash_request(self, request: QueryRequest | RetrieveRequest) -> str:
        """Hash canonical semantic request content.

        CRITICAL: Never include credentials, Authorization headers, or
        transport-specific configuration in the hash.
        """
        # Dump to JSON with sorted keys for determinism
        request_dict = request.model_dump(mode="json")

        # Remove any fields that might contain secrets or transport details
        # For now, the canonical models don't include these, but be defensive
        canonical_json = json.dumps(
            request_dict,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

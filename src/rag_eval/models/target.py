"""Target identity, advertised capabilities, and health models."""

from pydantic import ConfigDict, Field

from rag_eval.models.common import CanonicalModel, JsonDict
from rag_eval.models.enums import HealthState


class TargetInfo(CanonicalModel):
    """Identifying information for an evaluated target."""

    name: str
    version: str | None = None
    implementation: str | None = None
    target_id: str | None = None
    adapter_type: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class UsageCapabilities(CanonicalModel):
    """Usage information a target can expose."""

    tokens: bool = False
    cost: bool = False
    cpu: bool = False
    ram: bool = False
    gpu: bool = False
    vram: bool = False


class RetrievalMetadataCapabilities(CanonicalModel):
    """Retrieval fields a target can expose per retrieved item."""

    rank: bool = False
    score: bool = False
    document_id: bool = False
    chunk_id: bool = False
    page: bool = False
    character_span: bool = False


class TargetCapabilities(CanonicalModel):
    """Optional operations and observations supported by a target.

    Unknown optional fields are ignored to preserve minor v1 protocol
    compatibility while canonical known fields remain explicitly typed.
    """

    model_config = ConfigDict(extra="ignore")

    protocol_version: str = "1.0"
    target: TargetInfo
    query: bool = False
    streaming: bool = False
    conversation_history: bool = False
    retrieval: bool = False
    retrieval_stages: bool = False
    document_ingestion: bool = False
    chunk_ingestion: bool = False
    context_injection: bool = False
    citations: bool = False
    confidence: bool = False
    target_trace: bool = False
    effective_configuration: bool = False
    idempotency: bool = False
    request_recovery: bool = False
    usage: UsageCapabilities = Field(default_factory=UsageCapabilities)
    retrieval_metadata: RetrievalMetadataCapabilities = Field(
        default_factory=RetrievalMetadataCapabilities
    )
    limits: dict[str, int] = Field(default_factory=dict)
    idempotency_retention_seconds: int | None = Field(default=None, ge=0)
    metadata: JsonDict = Field(default_factory=dict)


class HealthStatus(CanonicalModel):
    """Operational target health, separate from evaluation correctness."""

    status: HealthState
    target: TargetInfo
    details: JsonDict = Field(default_factory=dict)

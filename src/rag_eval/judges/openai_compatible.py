"""OpenAI-compatible offline judge adapter.

The adapter is used only by metric scoring.  It receives persisted claims and
evidence and calls the configured judge endpoint; it never has access to the
evaluated target adapter.
"""

import json
import os
from typing import Any

import httpx

from rag_eval.models import Claim, ClaimAssessment, EvidenceAssessment
from rag_eval.models.common import SourceLocation


class OpenAICompatibleJudge:
    """Judge implementation for OpenAI and local OpenAI-compatible servers."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.parameters = parameters or {}

    async def assess_claims(
        self,
        claims: list[Claim],
        evidence: list[SourceLocation] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[ClaimAssessment]:
        """Ask the judge for JSON claim classifications."""
        payload = await self._complete(
            "Classify each claim as SUPPORTED, CONTRADICTED, UNSUPPORTED, or "
            "UNKNOWN. Return JSON array with claim_id, classification, score, "
            "confidence, supporting_evidence and contradicting_evidence.",
            {
                "claims": [claim.model_dump(mode="json") for claim in claims],
                "evidence": [item.model_dump(mode="json") for item in evidence or []],
                "context": context or {},
            },
        )
        return [ClaimAssessment.model_validate(item) for item in payload]

    async def assess_evidence_relationship(
        self,
        claim: Claim,
        evidence: SourceLocation,
        context: dict[str, Any] | None = None,
    ) -> EvidenceAssessment:
        """Ask the judge for one claim/evidence relationship."""
        payload = await self._complete(
            "Classify the evidence relationship as ENTAILS, CONTRADICTS, "
            "NEUTRAL, or UNKNOWN. Return one JSON object.",
            {
                "claim": claim.model_dump(mode="json"),
                "evidence": evidence.model_dump(mode="json"),
                "context": context or {},
            },
        )
        return EvidenceAssessment.model_validate(payload)

    async def _complete(self, instruction: str, data: dict[str, Any]) -> Any:
        """Submit a structured judge request and decode its JSON content."""
        response_format = {"type": "json_object"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(data)},
            ],
            "response_format": response_format,
            **self.parameters,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "results" in parsed:
            return parsed["results"]
        return parsed


def create_judge_adapter(config: dict[str, Any] | None) -> OpenAICompatibleJudge | None:
    """Build a judge from a portable config block, or return ``None``."""
    if not config:
        return None
    provider = str(config.get("provider") or "").lower()
    if provider in {"", "none", "ideal"}:
        return None
    if provider not in {
        "openai_compatible",
        "local_llm",
        "local-openai-compatible",
    }:
        raise ValueError(f"unsupported judge provider: {provider}")

    connection = dict(config.get("connection") or {})
    base_url = str(connection.get("base_url") or config.get("base_url") or "")
    if not base_url:
        raise ValueError("judge connection.base_url is required")
    secrets = dict(config.get("secrets") or {})
    api_key = secrets.get("api_key")
    if isinstance(api_key, str) and api_key.startswith("${"):
        api_key = None
    authentication_env = config.get("authentication_env")
    if not api_key and authentication_env:
        api_key = os.getenv(str(authentication_env))
    return OpenAICompatibleJudge(
        model=str(config.get("model") or "local-model"),
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=float(connection.get("timeout_seconds", 120.0)),
        parameters=dict(config.get("parameters") or {}),
    )

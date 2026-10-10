"""OpenAI-compatible offline judge adapter.

The adapter is used only by metric scoring.  It receives persisted claims and
evidence and calls the configured judge endpoint; it never has access to the
evaluated target adapter.
"""

import asyncio
import hashlib
import json
import os
import time
from typing import Any

import httpx

from rag_eval.judges.base import JudgeConfiguration
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
        configuration: JudgeConfiguration | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.parameters = parameters or {}
        self._configuration = configuration or JudgeConfiguration(
            model_id=model,
            timeout_seconds=timeout_seconds,
        )
        self.last_result: dict[str, Any] = {}
        self._cache: dict[str, Any] = {}

    @property
    def configuration(self) -> JudgeConfiguration:
        """Return the current non-secret judge configuration."""
        return self._configuration

    async def configure(self, configuration: JudgeConfiguration) -> None:
        """Replace configuration used by subsequent calls."""
        self._configuration = configuration
        self.model = configuration.model_id
        self.timeout_seconds = configuration.timeout_seconds

    async def assess_claims_batch(
        self,
        batches: list[tuple[list[Claim], list[SourceLocation] | None]],
        context: dict[str, Any] | None = None,
    ) -> list[list[ClaimAssessment]]:
        """Assess batches sequentially with bounded provider retries."""
        return [
            await self.assess_claims(claims, evidence, context)
            for claims, evidence in batches
        ]

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
        sanitized_data = self._sanitize_data(data)
        config_hash = hashlib.sha256(
            self.configuration.model_dump_json().encode()
        ).hexdigest()
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "instruction": instruction,
                    "data": sanitized_data,
                    "config_hash": config_hash,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if cache_key in self._cache:
            self.last_result = {
                "cache_key": cache_key,
                "config_hash": config_hash,
                "cached": True,
                "latency_ms": 0.0,
                "usage": {},
            }
            return self._cache[cache_key]

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": json.dumps(sanitized_data),
                },
            ],
            "response_format": response_format,
            "temperature": self.configuration.temperature,
            **self.parameters,
        }
        if self.configuration.max_tokens is not None:
            body.setdefault("max_tokens", self.configuration.max_tokens)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.perf_counter()
        last_error: Exception | None = None
        response = None
        for attempt in range(self.configuration.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=body,
                        headers=headers,
                    )
                    response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                break
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt >= self.configuration.retries:
                    raise ValueError(
                        "judge returned malformed structured output"
                    ) from exc
                await asyncio.sleep(min(2**attempt, 8))
        else:
            raise ValueError("judge request failed") from last_error
        self._cache[cache_key] = parsed
        self.last_result = {
            "cache_key": cache_key,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "usage": (response.json().get("usage", {}) if response is not None else {}),
            "config_hash": config_hash,
            "cached": False,
        }
        if isinstance(parsed, dict) and "results" in parsed:
            return parsed["results"]
        return parsed

    def _sanitize_data(self, value: Any) -> Any:
        """Remove benchmark reference answers unless explicitly permitted."""
        if self.configuration.allow_reference_answer:
            return value
        if isinstance(value, dict):
            return {
                key: self._sanitize_data(item)
                for key, item in value.items()
                if key not in {"reference_answer", "reference_answers"}
            }
        if isinstance(value, list):
            return [self._sanitize_data(item) for item in value]
        return value


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
        model=str(config.get("model_id") or config.get("model") or "local-model"),
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=float(connection.get("timeout_seconds", 120.0)),
        parameters=dict(config.get("parameters") or {}),
        configuration=JudgeConfiguration(
            provider=provider or "openai_compatible",
            model_id=str(
                config.get("model_id") or config.get("model") or "local-model"
            ),
            model_version=config.get("model_version"),
            prompt_id=str(config.get("prompt_id") or "default"),
            prompt_version=str(config.get("prompt_version") or "1"),
            temperature=float(config.get("temperature", 0.0)),
            max_tokens=config.get("max_tokens"),
            retries=int(config.get("retries", 2)),
            timeout_seconds=float(
                config.get(
                    "timeout_seconds",
                    connection.get("timeout_seconds", 120.0),
                )
            ),
        ),
    )

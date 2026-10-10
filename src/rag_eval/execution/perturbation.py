"""Versioned perturbation operators for robustness evaluation.

Perturbations are registered as pure functions over request text.  The
registry returns a new request payload and a stable pair descriptor, so a
robustness experiment never mutates the benchmark source case in place.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

PerturbationFunction = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class PerturbationDefinition:
    """Identity and implementation metadata for one perturbation operator."""

    perturbation_id: str
    version: str
    description: str
    apply: PerturbationFunction


class PerturbationRegistry:
    """Registry of pure, versioned robustness perturbation operators."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], PerturbationDefinition] = {}

    def register(self, definition: PerturbationDefinition) -> None:
        """Register a perturbation identity, rejecting duplicate versions."""
        key = (definition.perturbation_id, definition.version)
        if key in self._definitions:
            raise ValueError(f"perturbation already registered: {key}")
        self._definitions[key] = definition

    def get(self, perturbation_id: str, version: str = "1") -> PerturbationDefinition:
        """Return a registered perturbation or raise a clear configuration error."""
        try:
            return self._definitions[(perturbation_id, version)]
        except KeyError as exc:
            raise KeyError(
                f"unknown perturbation {perturbation_id!r} version {version!r}"
            ) from exc

    def list(self) -> list[PerturbationDefinition]:
        """Return definitions in stable identity order."""
        return sorted(
            self._definitions.values(),
            key=lambda definition: (definition.perturbation_id, definition.version),
        )

    def apply(
        self,
        payload: Mapping[str, Any],
        perturbation_id: str,
        *,
        version: str = "1",
    ) -> dict[str, Any]:
        """Create a perturbed request and attach its reproducible pair identity."""
        definition = self.get(perturbation_id, version)
        original = dict(payload)
        perturbed = definition.apply(dict(original))
        pair_id = hashlib.sha256(repr(sorted(original.items())).encode()).hexdigest()[
            :24
        ]
        perturbed["perturbation"] = {
            "perturbation_id": definition.perturbation_id,
            "version": definition.version,
            "pair_id": pair_id,
        }
        return perturbed


def _replace_text(
    payload: dict[str, Any], transform: Callable[[str], str]
) -> dict[str, Any]:
    result = dict(payload)
    if isinstance(result.get("query"), str):
        result["query"] = transform(result["query"])
    return result


def default_perturbation_registry() -> PerturbationRegistry:
    """Create the built-in deterministic robustness operator registry."""
    registry = PerturbationRegistry()
    registry.register(
        PerturbationDefinition(
            "query.whitespace_normalization",
            "1",
            "Collapse repeated whitespace in the query.",
            lambda payload: _replace_text(payload, lambda text: " ".join(text.split())),
        )
    )
    registry.register(
        PerturbationDefinition(
            "query.typo_removal",
            "1",
            "Remove punctuation to test punctuation robustness.",
            lambda payload: _replace_text(
                payload, lambda text: re.sub(r"[^\w\s]", "", text)
            ),
        )
    )
    registry.register(
        PerturbationDefinition(
            "query.case_flip",
            "1",
            "Invert query casing to test case robustness.",
            lambda payload: _replace_text(payload, lambda text: text.swapcase()),
        )
    )
    return registry


__all__ = [
    "PerturbationDefinition",
    "PerturbationRegistry",
    "default_perturbation_registry",
]

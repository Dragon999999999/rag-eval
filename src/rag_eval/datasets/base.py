"""Canonical benchmark dataset boundary for corpus preparation and registration."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from rag_eval.models import BenchmarkCase, BenchmarkManifest, Chunk, Document


class BenchmarkDataset(ABC):
    """Expose canonical benchmark records without coupling callers to file format.

    Dataset implementations may stream local files or later remote providers.
    Callers receive Stage 2 models and must not assume that all cases or chunks
    are held in memory.
    """

    @abstractmethod
    def load_manifest(self) -> BenchmarkManifest:
        """Return the validated canonical benchmark manifest."""

    @abstractmethod
    def iter_cases(self) -> Iterator[BenchmarkCase]:
        """Yield canonical benchmark cases lazily in source order."""

    @abstractmethod
    def iter_documents(self) -> Iterator[Document]:
        """Yield canonical source-document identities."""

    @abstractmethod
    def iter_chunks(self) -> Iterator[Chunk]:
        """Yield canonical evaluator-defined chunks lazily in source order."""

    @abstractmethod
    def validate(self) -> None:
        """Validate source integrity and cross-record benchmark invariants."""

    @abstractmethod
    def source_path(self, document: Document) -> Path | None:
        """Return the local source path for a document when one is configured."""

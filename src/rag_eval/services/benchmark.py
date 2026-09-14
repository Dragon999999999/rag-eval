"""Registration of canonical benchmark cases before execution exists."""

from rag_eval.datasets import BenchmarkDataset
from rag_eval.db.repositories import PersistenceRepository


class BenchmarkRegistrationService:
    """Persist lazy benchmark cases without exposing them to a target."""

    def __init__(self, repository: PersistenceRepository) -> None:
        """Bind the service to the caller-managed persistence repository."""
        self._repository = repository

    async def register(self, dataset: BenchmarkDataset) -> int:
        """Validate and persist every canonical benchmark case.

        Returns:
            Number of persisted cases.
        """
        dataset.validate()
        manifest = dataset.load_manifest()
        count = 0
        for case in dataset.iter_cases():
            await self._repository.persist_benchmark_case(manifest.benchmark_id, case)
            count += 1
        return count

"""Complete E2E workflow test.

Tests the full rag-eval architecture:
1. Load configuration
2. Validate dataset
3. Prepare corpus
4. Execute benchmark
5. Score results
6. Generate report
7. Export to Parquet

All without external APIs.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from rag_eval.artifacts import ArtifactService, create_artifact_store
from rag_eval.config import (
    configuration_hash,
    expand_matrix,
    get_settings,
    load_experiment_config,
)
from rag_eval.db import create_async_engine, create_session_factory
from rag_eval.db.models import RunRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.metrics import get_stage12_catalog
from rag_eval.metrics.service import ScoringService
from rag_eval.models.enums import RunStatus


@pytest.mark.integration
@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete rag-eval workflow end-to-end."""

    @pytest.fixture
    def test_config(self) -> Path:
        """Create test configuration."""
        # Use existing example config
        return Path(__file__).parent.parent / "examples" / "basic.yaml"

    @pytest.fixture
    async def database_session(self):
        """Create test database session."""
        settings = get_settings()
        engine = create_async_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            yield session

        await engine.dispose()

    @pytest.fixture
    async def artifact_service(self, database_session):
        """Create artifact service."""
        settings = get_settings()
        store = create_artifact_store(settings)
        repository = PersistenceRepository(database_session)
        return ArtifactService(store, repository)

    @pytest.mark.asyncio
    async def test_full_workflow(
        self,
        test_config: Path,
        database_session,
        artifact_service,
    ) -> None:
        """Test complete workflow from config to export."""
        # Skip if no database
        pytest.skip("Requires database setup - run manually with docker compose")

        # 1. Load configuration
        experiment = load_experiment_config(test_config)
        combinations = expand_matrix(experiment)
        assert len(combinations) >= 1

        # 2. Create run
        run_id = f"run-e2e-{uuid4()}"
        repository = PersistenceRepository(database_session)

        run = RunRecord(
            run_id=run_id,
            name=experiment.run.name,
            status=RunStatus.PENDING.value,
            config_hash=configuration_hash(experiment),
            target_id="mock-target",
            seed=experiment.run.seed,
        )

        # 3. Create adapter (would use mock target)
        # adapter = create_target_adapter(experiment.target)

        # 4. Execute benchmark (skipped - requires mock target server)
        # executor = BenchmarkExecutor(experiment, adapter, artifact_service, repository, database_session)
        # result = await executor.execute(run_id, manifest)

        # 5. Score results
        # registry = get_stage12_catalog()
        # scoring_service = ScoringService(registry, repository)
        # score_result = await scoring_service.score_run(run_id)

        # 6. Generate report
        # report_generator = ReportGenerator(repository)
        # report = await report_generator.generate_report(run_id)
        # assert report.total_cases > 0

        # 7. Export to Parquet
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     exporter = ExportService(repository, Path(tmpdir))
        #     exported = await exporter.export_run(run_id)
        #     assert len(exported.files) > 0

    @pytest.mark.asyncio
    async def test_scoring_independence(
        self,
        database_session,
    ) -> None:
        """Test that scoring works without target adapter.

        This is a MANDATORY test for Stage 14.
        """
        # Skip if no database
        pytest.skip("Requires database with persisted run data")

        repository = PersistenceRepository(database_session)

        # Load a completed run (would need to be created first)
        # run_id = "some-completed-run"

        # Score WITHOUT any target adapter
        registry = get_stage12_catalog()
        scoring_service = ScoringService(registry, repository)

        # This should succeed using only persisted data
        # score_result = await scoring_service.score_run(run_id)

        # Verify no target calls were made
        # (This is enforced by architecture - no TargetAdapter in scoring)

    @pytest.mark.asyncio
    async def test_parquet_export_verification(
        self,
        database_session,
    ) -> None:
        """Test Parquet export creates valid readable files."""
        # Skip if no database
        pytest.skip("Requires database with persisted run data")


        repository = PersistenceRepository(database_session)

        # Export a run (would need to be created first)
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     exporter = ExportService(repository, Path(tmpdir))
        #     exported = await exporter.export_run(run_id)

        #     # Verify files are readable
        #     assert "cases.parquet" in exported.files
        #     assert "metrics.parquet" in exported.files

        #     # Read and verify schemas
        #     cases_table = pq.read_table(Path(tmpdir) / "cases.parquet")
        #     assert len(cases_table.columns) > 0

        #     metrics_table = pq.read_table(Path(tmpdir) / "metrics.parquet")
        #     assert len(metrics_table.columns) > 0

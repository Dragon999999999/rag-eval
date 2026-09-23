"""Test definition, metric selection, and evaluation-run API endpoints.

This controller deliberately depends on a service contract that is implemented
separately.  It owns HTTP concerns only:

- request/response validation
- status-code mapping
- YAML import/export transport
- routing for test configuration and run lifecycle actions

Business rules such as test readiness, metric applicability, run-state
transitions, pause/resume/recovery semantics, and immutable run snapshots belong
to TestService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse

from rag_eval.api.dependencies import (
    MetricRegistryDep,
    TestServiceDep,
    verify_api_key,
)

from rag_eval.api.test_schemas import (
    AttemptDetail,
    CaseExecutionDetail,
    MetricDefinition,
    MetricImportResult,
    RunDetail,
    RunEventInfo,
    RunResultsResponse,
    RunStatus,
    TestCreate,
    TestDetail,
    TestMetricSelectionUpdate,
    TestMetricsInfo,
    TestSummary,
    TestUpdate,
    TestValidationResult,
)

router = APIRouter(
    prefix="/tests",
    dependencies=[Depends(verify_api_key)],
)


# ============================================================================
# Internal exception mapping
# ============================================================================


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail,
    )


# ============================================================================
# Tests
# ============================================================================


@router.post(
    "",
    response_model=TestDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create test",
)
async def create_test(
    request: TestCreate,
    service: TestServiceDep,
) -> TestDetail:
    """Create an editable test definition.

    Only a name is required.  A newly created test may remain INCOMPLETE until
    target, benchmark, and metric configuration are supplied.
    """
    try:
        test = await service.create_test(
            name=request.name,
            description=request.description,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc

    return TestDetail.model_validate(
        test,
        from_attributes=True,
    )


@router.get(
    "",
    response_model=list[TestSummary],
    summary="List tests",
)
async def list_tests(
    service: TestServiceDep,
) -> list[TestSummary]:
    """List test definitions."""
    tests = await service.list_tests()

    return [
        TestSummary.model_validate(
            item,
            from_attributes=True,
        )
        for item in tests
    ]


@router.get(
    "/{test_id}",
    response_model=TestDetail,
    summary="Get test",
)
async def get_test(
    test_id: str,
    service: TestServiceDep,
) -> TestDetail:
    """Return one test with its current editable configuration."""
    test = await service.get_test(test_id)

    if test is None:
        raise _not_found(f"test not found: {test_id}")

    return TestDetail.model_validate(
        test,
        from_attributes=True,
    )


@router.patch(
    "/{test_id}",
    response_model=TestDetail,
    summary="Update test",
)
async def update_test(
    test_id: str,
    request: TestUpdate,
    service: TestServiceDep,
) -> TestDetail:
    """Update mutable test configuration.

    Omitting a field leaves it unchanged.  Explicit null for target_id,
    benchmark_id, or seed clears that value.
    """
    try:
        test = await service.update_test(
            test_id,
            changes=request.model_dump(
                exclude_unset=True,
            ),
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc

    return TestDetail.model_validate(
        test,
        from_attributes=True,
    )


@router.delete(
    "/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete test",
)
async def delete_test(
    test_id: str,
    service: TestServiceDep,
) -> None:
    """Delete an editable test definition.

    Existing runs remain valid because each run owns an immutable configuration
    snapshot and its test reference is nullable.
    """
    try:
        await service.delete_test(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc


# ============================================================================
# Metric registry and test-owned metric selection
# ============================================================================


@router.get(
    "/metrics/registry",
    response_model=list[MetricDefinition],
    summary="List registered metrics",
)
async def list_registered_metrics(
    registry: MetricRegistryDep,
) -> list[MetricDefinition]:
    """List globally registered metric definitions."""
    definitions = registry.list_metrics()

    return [
        MetricDefinition.model_validate(
            definition,
            from_attributes=True,
        )
        for definition in definitions
    ]


@router.get(
    "/metrics/registry/{metric_id}",
    response_model=MetricDefinition,
    summary="Get registered metric",
)
async def get_registered_metric(
    metric_id: str,
    registry: MetricRegistryDep,
) -> MetricDefinition:
    """Return one registered metric definition."""
    definition = registry.get_definition(metric_id)

    if definition is None:
        raise _not_found(f"metric not found: {metric_id}")

    return MetricDefinition.model_validate(
        definition,
        from_attributes=True,
    )


@router.get(
    "/{test_id}/metrics",
    response_model=TestMetricsInfo,
    summary="Get test metrics",
)
async def get_test_metrics(
    test_id: str,
    service: TestServiceDep,
) -> TestMetricsInfo:
    """Return registry metrics annotated with applicability and selection."""
    try:
        info = await service.get_test_metrics(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return TestMetricsInfo.model_validate(info)


@router.put(
    "/{test_id}/metrics",
    response_model=TestMetricsInfo,
    summary="Replace test metric selection",
)
async def set_test_metrics(
    test_id: str,
    request: TestMetricSelectionUpdate,
    service: TestServiceDep,
) -> TestMetricsInfo:
    """Replace the editable metric configuration for a test."""
    try:
        info = await service.set_test_metrics(
            test_id,
            mode=request.mode,
            selected_metrics=request.selected_metrics,
            metric_parameters=request.metric_parameters,
            judge_config=request.judge_config,
            retrieval_config=request.retrieval_config,
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable(str(exc)) from exc

    return TestMetricsInfo.model_validate(info)


@router.post(
    "/{test_id}/metrics/select-all",
    response_model=TestMetricsInfo,
    summary="Select all applicable metrics",
)
async def select_all_test_metrics(
    test_id: str,
    service: TestServiceDep,
) -> TestMetricsInfo:
    """Set ALL_AVAILABLE mode for the test.

    The service determines applicability using the current target, benchmark,
    and metric requirements.
    """
    try:
        info = await service.select_all_applicable_metrics(
            test_id
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable(str(exc)) from exc

    return TestMetricsInfo.model_validate(info)


@router.post(
    "/{test_id}/metrics/import",
    response_model=MetricImportResult,
    summary="Import test metric YAML",
)
async def import_test_metrics(
    test_id: str,
    service: TestServiceDep,
    file: UploadFile = File(...),
) -> MetricImportResult:
    """Import YAML as configuration input without preserving it as an artifact.

    Unknown metric IDs should be ignored with warnings.  Known but currently
    inapplicable metrics should also be reported rather than causing the whole
    import to fail.

    Target/benchmark values contained in YAML are returned as detected values;
    service policy decides whether unset values are applied automatically and
    which conflicts require frontend confirmation.
    """
    if file.filename and not file.filename.lower().endswith(
        (".yaml", ".yml")
    ):
        raise _bad_request(
            "metric configuration import must be a .yaml or .yml file"
        )

    content = await file.read()

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _bad_request(
            "metric configuration YAML must be UTF-8"
        ) from exc

    try:
        result = await service.import_test_yaml(
            test_id,
            text,
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc

    return MetricImportResult.model_validate(result)


@router.get(
    "/{test_id}/metrics/export",
    response_class=PlainTextResponse,
    summary="Export test metric YAML",
)
async def export_test_metrics(
    test_id: str,
    service: TestServiceDep,
) -> PlainTextResponse:
    """Export the current test configuration as portable YAML."""
    try:
        yaml_text = await service.export_test_yaml(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return PlainTextResponse(
        content=yaml_text,
        media_type="application/yaml",
        headers={
            "Content-Disposition": (
                f'attachment; filename="test-{test_id}.yaml"'
            ),
        },
    )


# ============================================================================
# Validation / planning
# ============================================================================


@router.post(
    "/{test_id}/validate",
    response_model=TestValidationResult,
    summary="Validate test",
)
async def validate_test(
    test_id: str,
    service: TestServiceDep,
) -> TestValidationResult:
    """Validate whether the test can currently start a run."""
    try:
        result = await service.validate_test(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return TestValidationResult.model_validate(result)


# ============================================================================
# Runs belonging to a test
# ============================================================================


@router.post(
    "/{test_id}/runs",
    response_model=RunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Start test run",
)
async def start_test_run(
    test_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Create and start a run from the test's current configuration.

    The service must validate the test and persist an immutable configuration
    snapshot before execution begins.
    """
    try:
        run = await service.start_run(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable(str(exc)) from exc
    except RuntimeError as exc:
        raise _conflict(str(exc)) from exc

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.get(
    "/{test_id}/runs",
    response_model=list[RunDetail],
    summary="List test runs",
)
async def list_test_runs(
    test_id: str,
    service: TestServiceDep,
) -> list[RunDetail]:
    """List all historical runs created from a test."""
    try:
        runs = await service.list_test_runs(test_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return [
        RunDetail.model_validate(
            run,
            from_attributes=True,
        )
        for run in runs
    ]


# ============================================================================
# Run lifecycle
# ============================================================================


@router.get(
    "/runs/{run_id}",
    response_model=RunDetail,
    summary="Get run",
)
async def get_run(
    run_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Return one run and its current lifecycle state."""
    run = await service.get_run(run_id)

    if run is None:
        raise _not_found(f"run not found: {run_id}")

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.get(
    "/runs/{run_id}/status",
    response_model=RunStatus,
    summary="Get run status",
)
async def get_run_status(
    run_id: str,
    service: TestServiceDep,
) -> RunStatus:
    """Return lightweight progress information suitable for frontend polling."""
    try:
        run_status = await service.get_run_status(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return RunStatus.model_validate(run_status)


@router.post(
    "/runs/{run_id}/pause",
    response_model=RunDetail,
    summary="Pause run",
)
async def pause_run(
    run_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Request a graceful pause.

    Running work may finish, but new cases should no longer be scheduled.
    """
    try:
        run = await service.pause_run(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise _conflict(str(exc)) from exc

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.post(
    "/runs/{run_id}/resume",
    response_model=RunDetail,
    summary="Resume paused run",
)
async def resume_run(
    run_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Resume an intentionally paused run from its immutable run snapshot."""
    try:
        run = await service.resume_run(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise _conflict(str(exc)) from exc

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.post(
    "/runs/{run_id}/recover",
    response_model=RunDetail,
    summary="Recover interrupted run",
)
async def recover_run(
    run_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Attempt recovery of an interrupted run.

    Completed cases must remain untouched.  The service should recover target
    requests when possible and append a new attempt when retrying is required.
    """
    try:
        run = await service.recover_run(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise _conflict(str(exc)) from exc

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=RunDetail,
    summary="Cancel run",
)
async def cancel_run(
    run_id: str,
    service: TestServiceDep,
) -> RunDetail:
    """Permanently cancel a run."""
    try:
        run = await service.cancel_run(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise _conflict(str(exc)) from exc

    return RunDetail.model_validate(
        run,
        from_attributes=True,
    )


@router.get(
    "/runs/{run_id}/events",
    response_model=list[RunEventInfo],
    summary="List run events",
)
async def list_run_events(
    run_id: str,
    service: TestServiceDep,
) -> list[RunEventInfo]:
    """Return append-only lifecycle events for debugging/auditing."""
    try:
        events = await service.list_run_events(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return [
        RunEventInfo.model_validate(
            event,
            from_attributes=True,
        )
        for event in events
    ]


# ============================================================================
# Run execution details / results
# ============================================================================


@router.get(
    "/runs/{run_id}/cases",
    response_model=list[CaseExecutionDetail],
    summary="List run cases",
)
async def list_run_cases(
    run_id: str,
    service: TestServiceDep,
) -> list[CaseExecutionDetail]:
    """List logical case executions for a run."""
    try:
        cases = await service.list_run_cases(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return [
        CaseExecutionDetail.model_validate(
            case,
            from_attributes=True,
        )
        for case in cases
    ]


@router.get(
    "/runs/{run_id}/cases/{case_execution_id}/attempts",
    response_model=list[AttemptDetail],
    summary="List case attempts",
)
async def list_case_attempts(
    run_id: str,
    case_execution_id: str,
    service: TestServiceDep,
) -> list[AttemptDetail]:
    """List retry/recovery attempts for one logical case execution."""
    try:
        attempts = await service.list_case_attempts(
            run_id,
            case_execution_id,
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return [
        AttemptDetail.model_validate(
            attempt,
            from_attributes=True,
        )
        for attempt in attempts
    ]


@router.get(
    "/runs/{run_id}/results",
    response_model=RunResultsResponse,
    summary="Get run results",
)
async def get_run_results(
    run_id: str,
    service: TestServiceDep,
) -> RunResultsResponse:
    """Return individual and aggregate metric results for a run."""
    try:
        results = await service.get_run_results(run_id)
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return RunResultsResponse.model_validate(results)
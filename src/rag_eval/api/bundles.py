"""HTTP transport for portable `.rzip` bundles."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from rag_eval.api.dependencies import BundleServiceDep, verify_api_key

router = APIRouter(
    prefix="/bundles",
    dependencies=[Depends(verify_api_key)],
)


@router.get("/targets/{target_id}", summary="Export a target bundle")
async def export_target_bundle(target_id: str, service: BundleServiceDep) -> Response:
    """Download one target configuration as a checksummed `.rzip`."""
    try:
        data = await service.export_target(target_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{target_id}.rzip"'},
    )


@router.get("/benchmarks/{benchmark_id}", summary="Export a benchmark bundle")
async def export_benchmark_bundle(
    benchmark_id: str,
    service: BundleServiceDep,
) -> Response:
    """Download one benchmark and its document bytes."""
    try:
        data = await service.export_benchmark(benchmark_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{benchmark_id}.rzip"'},
    )


@router.get("/tests/{test_id}", summary="Export a test bundle")
async def export_test_bundle(
    test_id: str,
    service: BundleServiceDep,
    run_id: str | None = None,
) -> Response:
    """Download canonical test configuration, optionally with raw results."""
    try:
        data = await service.export_test(test_id, run_id=run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{test_id}.rzip"'},
    )


@router.get("/runs/{run_id}", summary="Export an evaluation bundle")
async def export_run_bundle(run_id: str, service: BundleServiceDep) -> Response:
    """Download an evaluation's immutable snapshot and raw observations."""
    try:
        data = await service.export_run(run_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.rzip"'},
    )


@router.post("/import", summary="Import a portable bundle")
async def import_bundle(
    service: BundleServiceDep,
    bundle: UploadFile = File(...),  # noqa: B008
) -> dict[str, object]:
    """Verify and import resources from an uploaded `.rzip`."""
    try:
        result = await service.import_bundle(await bundle.read())
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return asdict(result)

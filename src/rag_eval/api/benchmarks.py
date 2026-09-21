"""REST API for canonical benchmark management."""

import json
import mimetypes
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError

from rag_eval.api.dependencies import (
    ArtifactServiceDep,
    BenchmarkServiceDep,
)
from rag_eval.api.schemas import BenchmarkCreate, BenchmarkInfo
from rag_eval.models import (
    ArtifactType,
    Benchmark,
    BenchmarkCase,
    Chunk,
    CorpusMode,
    Document,
)

router = APIRouter(
    prefix="/benchmarks",
)

RecordT = TypeVar(
    "RecordT",
    BenchmarkCase,
    Chunk,
)


# ============================================================================
# Benchmark creation / retrieval
# ============================================================================


@router.post(
    "",
    response_model=BenchmarkInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark(
    request: BenchmarkCreate,
    service: BenchmarkServiceDep,
) -> BenchmarkInfo:
    """Create an empty benchmark."""
    try:
        benchmark = await service.create(
            name=request.name,
            version=request.version,
            corpus_mode=CorpusMode(request.corpus_mode),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _benchmark_info(benchmark)


@router.get(
    "/{benchmark_id}",
    response_model=BenchmarkInfo,
)
async def get_benchmark(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> BenchmarkInfo:
    """Return a complete benchmark summary."""
    benchmark = await _get_benchmark(
        service,
        benchmark_id,
    )

    return _benchmark_info(benchmark)


# ============================================================================
# Convenience create-with-files endpoint
# ============================================================================


@router.post(
    "/from-files",
    response_model=BenchmarkInfo,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_from_files(
    service: BenchmarkServiceDep,
    artifact_service: ArtifactServiceDep,
    name: str = Form(...),
    version: str = Form("1"),
    corpus_mode: str = Form("DOCUMENTS"),
    cases: list[UploadFile] | None = File(None),
    documents: list[UploadFile] | None = File(None),
    chunks: list[UploadFile] | None = File(None),
) -> BenchmarkInfo:
    """Create a benchmark and optionally upload its contents."""
    try:
        mode = CorpusMode(corpus_mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid corpus mode: {corpus_mode}",
        ) from exc

    case_files = cases or []
    document_files = documents or []
    chunk_files = chunks or []

    _validate_uploaded_modes(
        mode,
        document_files=document_files,
        chunk_files=chunk_files,
    )

    benchmark = await service.create(
        name=name,
        version=version,
        corpus_mode=mode,
    )

    benchmark_id = benchmark.manifest.benchmark_id

    await _add_case_uploads(
        service,
        benchmark_id,
        case_files,
    )

    await _add_document_uploads(
        service,
        artifact_service,
        benchmark_id,
        document_files,
    )

    await _add_chunk_uploads(
        service,
        benchmark_id,
        chunk_files,
    )

    return _benchmark_info(
        await service.get(benchmark_id)
    )


# ============================================================================
# Cases
# ============================================================================


@router.post(
    "/{benchmark_id}/cases",
    response_model=BenchmarkInfo,
)
async def add_benchmark_cases(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Add JSON or JSONL benchmark cases."""
    await _get_benchmark(
        service,
        benchmark_id,
    )

    await _add_case_uploads(
        service,
        benchmark_id,
        files,
    )

    return _benchmark_info(
        await service.get(benchmark_id)
    )


# ============================================================================
# Documents
# ============================================================================


@router.post(
    "/{benchmark_id}/documents",
    response_model=BenchmarkInfo,
)
async def add_benchmark_documents(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    artifact_service: ArtifactServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Store and attach source documents to a benchmark."""
    await _get_benchmark(
        service,
        benchmark_id,
    )

    await _add_document_uploads(
        service,
        artifact_service,
        benchmark_id,
        files,
    )

    return _benchmark_info(
        await service.get(benchmark_id)
    )


# ============================================================================
# Chunks
# ============================================================================


@router.post(
    "/{benchmark_id}/chunks",
    response_model=BenchmarkInfo,
)
async def add_benchmark_chunks(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Add canonical JSON or JSONL chunks."""
    await _get_benchmark(
        service,
        benchmark_id,
    )

    await _add_chunk_uploads(
        service,
        benchmark_id,
        files,
    )

    return _benchmark_info(
        await service.get(benchmark_id)
    )


# ============================================================================
# Internal helpers
# ============================================================================


async def _get_benchmark(
    service: BenchmarkServiceDep,
    benchmark_id: str,
) -> Benchmark:
    try:
        return await service.get(benchmark_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


async def _add_case_uploads(
    service: BenchmarkServiceDep,
    benchmark_id: str,
    files: list[UploadFile],
) -> int:
    count = 0

    for upload in files:
        data = await upload.read()

        cases = _parse_uploaded_records(
            data=data,
            filename=upload.filename or "cases.json",
            model_type=BenchmarkCase,
            record_name="case",
        )

        count += await service.add_cases(
            benchmark_id,
            cases,
        )

    return count


async def _add_document_uploads(
    service: BenchmarkServiceDep,
    artifact_service: ArtifactServiceDep,
    benchmark_id: str,
    files: list[UploadFile],
) -> int:
    count = 0

    for upload in files:
        filename = upload.filename or "document"

        mime_type = (
            upload.content_type
            or mimetypes.guess_type(filename)[0]
        )

        await upload.seek(0)

        artifact = await artifact_service.put(
            upload.file,
            ArtifactType.SOURCE_DOCUMENT,
            content_type=mime_type,
            metadata={
                "filename": filename,
                "benchmark_id": benchmark_id,
            },
        )

        document = Document(
            document_id=f"document-{uuid4()}",
            filename=filename,
            mime_type=mime_type,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            artifact=artifact,
        )

        await service.add_document(
            benchmark_id,
            document,
        )

        count += 1

    return count


async def _add_chunk_uploads(
    service: BenchmarkServiceDep,
    benchmark_id: str,
    files: list[UploadFile],
) -> int:
    count = 0

    for upload in files:
        data = await upload.read()

        chunks = _parse_uploaded_records(
            data=data,
            filename=upload.filename or "chunks.json",
            model_type=Chunk,
            record_name="chunk",
        )

        count += await service.add_chunks(
            benchmark_id,
            chunks,
        )

    return count


def _parse_uploaded_records(
    *,
    data: bytes,
    filename: str,
    model_type: type[RecordT],
    record_name: str,
) -> list[RecordT]:
    """Parse JSON or JSONL into canonical Pydantic records."""
    text = data.decode("utf-8")

    try:
        if Path(filename).suffix.lower() == ".jsonl":
            records: list[RecordT] = []

            for line_number, line in enumerate(
                text.splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue

                try:
                    raw = json.loads(line)
                    records.append(
                        model_type.model_validate(raw)
                    )
                except (
                    json.JSONDecodeError,
                    ValidationError,
                ) as exc:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"invalid {record_name} at "
                            f"{filename}:{line_number}: {exc}"
                        ),
                    ) from exc

            return records

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid JSON in {filename}: {exc}",
            ) from exc

        if not isinstance(payload, list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{filename} must contain a JSON array "
                    f"or use JSONL"
                ),
            )

        try:
            return [
                model_type.model_validate(record)
                for record in payload
            ]
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid {record_name} in {filename}: {exc}",
            ) from exc

    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{filename} must be UTF-8 encoded",
        ) from exc


def _validate_uploaded_modes(
    mode: CorpusMode,
    *,
    document_files: list[UploadFile],
    chunk_files: list[UploadFile],
) -> None:
    if mode is CorpusMode.DOCUMENTS and chunk_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "CHUNKS files cannot be supplied to a "
                "DOCUMENTS benchmark"
            ),
        )

    if mode is CorpusMode.CHUNKS and document_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "document files cannot be supplied to a "
                "CHUNKS benchmark"
            ),
        )

    if mode is CorpusMode.EXTERNAL and (
        document_files or chunk_files
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "EXTERNAL benchmarks cannot contain "
                "documents or chunks"
            ),
        )


def _benchmark_info(
    benchmark: Benchmark,
) -> BenchmarkInfo:
    manifest = benchmark.manifest

    return BenchmarkInfo(
        benchmark_id=manifest.benchmark_id,
        name=manifest.name,
        version=manifest.version,
        schema_version=manifest.schema_version,
        corpus_mode=manifest.corpus_mode.value,
        content_hash=manifest.content_hash,
        corpus_id=manifest.corpus_id,
        source=manifest.source,
        tags=manifest.tags,
        metadata=manifest.metadata,
        case_count=benchmark.case_count,
        document_count=benchmark.document_count,
        chunk_count=benchmark.chunk_count,
        is_complete=benchmark.is_complete,
        available_corpus_modes=sorted(
            mode.value
            for mode in benchmark.available_corpus_modes
        ),
        created_at=manifest.created_at,
    )
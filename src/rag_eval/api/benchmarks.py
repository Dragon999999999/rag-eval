"""REST API for canonical benchmark management."""

import json
import mimetypes
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ValidationError

from rag_eval.api.dependencies import (
    ArtifactServiceDep,
    BenchmarkServiceDep,
)
from rag_eval.api.schemas import (
    BenchmarkCreate,
    BenchmarkInfo,
)
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


class CorpusModeUpdate(BaseModel):
    """Request to change benchmark corpus representation."""

    corpus_mode: CorpusMode


# ============================================================================
# Benchmarks
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
            corpus_mode=CorpusMode(
                request.corpus_mode
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _benchmark_info(benchmark)


@router.get(
    "",
    response_model=list[BenchmarkInfo],
)
async def list_benchmarks(
    service: BenchmarkServiceDep,
) -> list[BenchmarkInfo]:
    """List all persisted benchmarks."""
    records = await service.list_benchmarks()

    result: list[BenchmarkInfo] = []

    for record in records:
        benchmark = await service.get(
            record.benchmark_id
        )

        result.append(
            _benchmark_info(benchmark)
        )

    return result


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
    """Create a benchmark and optionally import contents."""
    try:
        mode = CorpusMode(corpus_mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"invalid corpus mode: {corpus_mode}"
            ),
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

    benchmark_id = (
        benchmark.manifest.benchmark_id
    )

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


@router.get(
    "/{benchmark_id}",
    response_model=BenchmarkInfo,
)
async def get_benchmark(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> BenchmarkInfo:
    """Return benchmark summary."""
    benchmark = await _get_benchmark(
        service,
        benchmark_id,
    )

    return _benchmark_info(benchmark)


@router.delete(
    "/{benchmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_benchmark(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> Response:
    """Delete one benchmark."""
    try:
        await service.delete(
            benchmark_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.put(
    "/{benchmark_id}/corpus-mode",
    response_model=BenchmarkInfo,
)
async def change_corpus_mode(
    benchmark_id: str,
    request: CorpusModeUpdate,
    service: BenchmarkServiceDep,
) -> BenchmarkInfo:
    """Change DOCUMENTS/CHUNKS representation."""
    try:
        benchmark = await service.set_corpus_mode(
            benchmark_id,
            request.corpus_mode,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return _benchmark_info(benchmark)


# ============================================================================
# Cases
# ============================================================================


@router.get(
    "/{benchmark_id}/cases",
    response_model=list[BenchmarkCase],
)
async def list_benchmark_cases(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> list[BenchmarkCase]:
    """Return only the cases of a benchmark."""
    try:
        cases = await service.list_cases(
            benchmark_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return list(cases)


@router.post(
    "/{benchmark_id}/cases",
    response_model=BenchmarkCase,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_case(
    benchmark_id: str,
    case: BenchmarkCase,
    service: BenchmarkServiceDep,
) -> BenchmarkCase:
    """Create one normalized benchmark case."""
    try:
        return await service.create_case(
            benchmark_id,
            case,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{benchmark_id}/cases/import",
    response_model=BenchmarkInfo,
)
async def import_benchmark_cases(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Import cases from JSON/JSONL files."""
    try:
        await service.get_manifest(
            benchmark_id
        )

        await _add_case_uploads(
            service,
            benchmark_id,
            files,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _benchmark_info(
        await service.get(benchmark_id)
    )


@router.get(
    "/{benchmark_id}/cases/{case_id}",
    response_model=BenchmarkCase,
)
async def get_benchmark_case(
    benchmark_id: str,
    case_id: str,
    service: BenchmarkServiceDep,
) -> BenchmarkCase:
    """Return one benchmark case."""
    try:
        return await service.get_case(
            benchmark_id,
            case_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{benchmark_id}/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_benchmark_case(
    benchmark_id: str,
    case_id: str,
    service: BenchmarkServiceDep,
) -> Response:
    """Delete one benchmark case."""
    try:
        await service.delete_case(
            benchmark_id,
            case_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


# ============================================================================
# Documents
# ============================================================================


@router.get(
    "/{benchmark_id}/documents",
    response_model=list[Document],
)
async def list_benchmark_documents(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> list[Document]:
    """Return only benchmark documents."""
    try:
        documents = await service.list_documents(
            benchmark_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return list(documents)


@router.post(
    "/{benchmark_id}/documents",
    response_model=BenchmarkInfo,
    status_code=status.HTTP_201_CREATED,
)
async def add_benchmark_documents(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    artifact_service: ArtifactServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Upload atomic documents."""
    try:
        await _add_document_uploads(
            service,
            artifact_service,
            benchmark_id,
            files,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _benchmark_info(
        await service.get(benchmark_id)
    )


@router.get(
    "/{benchmark_id}/documents/{document_id}",
    response_model=Document,
)
async def get_benchmark_document(
    benchmark_id: str,
    document_id: str,
    service: BenchmarkServiceDep,
) -> Document:
    """Return one benchmark document."""
    try:
        return await service.get_document(
            benchmark_id,
            document_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{benchmark_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_benchmark_document(
    benchmark_id: str,
    document_id: str,
    service: BenchmarkServiceDep,
) -> Response:
    """Delete one benchmark document reference."""
    try:
        await service.delete_document(
            benchmark_id,
            document_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


# ============================================================================
# Chunks
# ============================================================================


@router.get(
    "/{benchmark_id}/chunks",
    response_model=list[Chunk],
)
async def list_benchmark_chunks(
    benchmark_id: str,
    service: BenchmarkServiceDep,
) -> list[Chunk]:
    """Return only benchmark chunks."""
    try:
        chunks = await service.list_chunks(
            benchmark_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return list(chunks)


@router.post(
    "/{benchmark_id}/chunks",
    response_model=Chunk,
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_chunk(
    benchmark_id: str,
    chunk: Chunk,
    service: BenchmarkServiceDep,
) -> Chunk:
    """Create one normalized chunk."""
    try:
        return await service.create_chunk(
            benchmark_id,
            chunk,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{benchmark_id}/chunks/import",
    response_model=BenchmarkInfo,
)
async def import_benchmark_chunks(
    benchmark_id: str,
    service: BenchmarkServiceDep,
    files: list[UploadFile] = File(...),
) -> BenchmarkInfo:
    """Import canonical chunks from JSON/JSONL."""
    try:
        await _add_chunk_uploads(
            service,
            benchmark_id,
            files,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _benchmark_info(
        await service.get(benchmark_id)
    )


@router.get(
    "/{benchmark_id}/chunks/{chunk_id}",
    response_model=Chunk,
)
async def get_benchmark_chunk(
    benchmark_id: str,
    chunk_id: str,
    service: BenchmarkServiceDep,
) -> Chunk:
    """Return one benchmark chunk."""
    try:
        return await service.get_chunk(
            benchmark_id,
            chunk_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{benchmark_id}/chunks/{chunk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_benchmark_chunk(
    benchmark_id: str,
    chunk_id: str,
    service: BenchmarkServiceDep,
) -> Response:
    """Delete one normalized chunk."""
    try:
        await service.delete_chunk(
            benchmark_id,
            chunk_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


# ============================================================================
# Upload helpers
# ============================================================================


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
            filename=(
                upload.filename
                or "cases.json"
            ),
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
    await service.get_manifest(
        benchmark_id
    )

    count = 0

    for upload in files:
        filename = (
            upload.filename
            or "document"
        )

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

        await service.create_document(
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
            filename=(
                upload.filename
                or "chunks.json"
            ),
            model_type=Chunk,
            record_name="chunk",
        )

        count += await service.add_chunks(
            benchmark_id,
            chunks,
        )

    return count


# ============================================================================
# Parsing
# ============================================================================


def _parse_uploaded_records(
    *,
    data: bytes,
    filename: str,
    model_type: type[RecordT],
    record_name: str,
) -> list[RecordT]:
    """Parse JSON/JSONL import containers."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                f"{filename} must be UTF-8 encoded"
            ),
        ) from exc

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
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"invalid {record_name} at "
                        f"{filename}:{line_number}: "
                        f"{exc}"
                    ),
                ) from exc

        return records

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                f"invalid JSON in {filename}: {exc}"
            ),
        ) from exc

    if not isinstance(payload, list):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                f"{filename} must contain a JSON array "
                "or use JSONL"
            ),
        )

    try:
        return [
            model_type.model_validate(record)
            for record in payload
        ]
    except ValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                f"invalid {record_name} in "
                f"{filename}: {exc}"
            ),
        ) from exc


# ============================================================================
# Validation / representation
# ============================================================================


def _validate_uploaded_modes(
    mode: CorpusMode,
    *,
    document_files: list[UploadFile],
    chunk_files: list[UploadFile],
) -> None:
    if (
        mode is CorpusMode.DOCUMENTS
        and chunk_files
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "chunk files cannot be supplied to "
                "a DOCUMENTS benchmark"
            ),
        )

    if (
        mode is CorpusMode.CHUNKS
        and document_files
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "documents cannot be supplied to "
                "a CHUNKS benchmark"
            ),
        )

    if (
        mode is CorpusMode.EXTERNAL
        and (
            document_files
            or chunk_files
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "EXTERNAL benchmarks cannot contain "
                "documents or chunks"
            ),
        )


async def _get_benchmark(
    service: BenchmarkServiceDep,
    benchmark_id: str,
) -> Benchmark:
    try:
        return await service.get(
            benchmark_id
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


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
            for mode
            in benchmark.available_corpus_modes
        ),
        created_at=manifest.created_at,
    )
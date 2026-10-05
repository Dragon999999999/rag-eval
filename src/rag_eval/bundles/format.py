"""Versioned ZIP format primitives for portable rag-eval resources.

This module deliberately contains no database assumptions.  Services can use
the writer and reader for target, benchmark, test, or full bundles while the
envelope and checksum behavior stays identical.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

import yaml

SUPPORTED_SCHEMA_VERSION = "1"
PACKAGE_FILENAME = "package.yaml"
CHECKSUM_FILENAME = "checksums.sha256"
_SECRET_PATTERN = re.compile(r"^\$\{RAG_EVAL_SECRET:([A-Za-z0-9_.-]+)\}$")


class BundleError(ValueError):
    """Raised when a bundle is malformed, unsupported, or tampered with."""


@dataclass(frozen=True)
class BundleImportResult:
    """Structured result for a bundle import operation."""

    created: list[dict[str, Any]] = field(default_factory=list)
    remapped: dict[str, str] = field(default_factory=dict)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    secret_missing: list[str] = field(default_factory=list)


def _safe_name(name: str) -> str:
    """Validate and normalize a ZIP member name."""
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise BundleError(f"unsafe bundle path: {name!r}")
    normalized = str(path)
    if normalized != name or "\\" in name:
        raise BundleError(f"non-canonical bundle path: {name!r}")
    return normalized


def _yaml_bytes(value: dict[str, Any]) -> bytes:
    """Serialize YAML in a stable UTF-8 representation."""
    return yaml.safe_dump(
        value,
        sort_keys=False,
        allow_unicode=True,
    ).encode("utf-8")


def content_hash(
    manifest: dict[str, Any],
    resources: dict[str, bytes],
) -> str:
    """Hash canonical manifest content and all resource bytes deterministically."""
    manifest_copy = dict(manifest)
    manifest_copy.pop("content_hash", None)
    digest_input = {
        "manifest": manifest_copy,
        "resources": {
            name: hashlib.sha256(resources[name]).hexdigest()
            for name in sorted(resources)
        },
    }
    return hashlib.sha256(
        json.dumps(
            digest_input,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def benchmark_content_hash(
    manifest: dict[str, Any],
    cases: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> str:
    """Hash portable benchmark metadata, truth, and document identities."""
    manifest_copy = dict(manifest)
    manifest_copy.pop("content_hash", None)
    document_hashes = [
        {
            key: document.get(key)
            for key in ("document_id", "filename", "mime_type", "sha256", "size_bytes")
        }
        | {"metadata": document.get("metadata", {})}
        for document in documents
    ]
    payload = {
        "manifest": manifest_copy,
        "cases": cases,
        "documents": document_hashes,
        "chunks": chunks,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


class BundleWriter:
    """Build a self-contained, checksummed `.rzip` bundle in memory."""

    def __init__(
        self,
        *,
        kind: str = "full",
        tool_version: str = "development",
        resources: dict[str, list[str]] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.kind = kind
        self.tool_version = tool_version
        self.created_at = created_at or datetime.now(UTC)
        self.resources = resources or {"targets": [], "benchmarks": [], "tests": []}
        self._entries: dict[str, bytes] = {}

    def add_bytes(self, name: str, data: bytes) -> None:
        """Add one safe relative file to the bundle."""
        safe_name = _safe_name(name)
        if safe_name in {PACKAGE_FILENAME, CHECKSUM_FILENAME}:
            raise BundleError(f"reserved bundle member: {safe_name}")
        self._entries[safe_name] = bytes(data)

    def add_text(self, name: str, value: str) -> None:
        """Add UTF-8 text to the bundle."""
        self.add_bytes(name, value.encode("utf-8"))

    def add_yaml(self, name: str, value: dict[str, Any]) -> None:
        """Add a YAML mapping to the bundle."""
        self.add_bytes(name, _yaml_bytes(value))

    def build(self) -> bytes:
        """Return the complete ZIP archive with envelope and checksums."""
        package = {
            "schema_version": SUPPORTED_SCHEMA_VERSION,
            "format": "rag-eval-bundle",
            "kind": self.kind,
            "tool_version": self.tool_version,
            "created_at": self.created_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "resources": self.resources,
        }
        package_bytes = _yaml_bytes(package)
        checksummed = {PACKAGE_FILENAME: package_bytes, **self._entries}
        checksum_text = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n"
            for name, data in sorted(checksummed.items())
        )
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(checksummed.items()):
                archive.writestr(name, data)
            archive.writestr(CHECKSUM_FILENAME, checksum_text.encode("ascii"))
        return output.getvalue()


class BundleReader:
    """Read and verify a portable `.rzip` archive."""

    def __init__(self, data: bytes) -> None:
        self._archive = zipfile.ZipFile(io.BytesIO(data))
        self._names = {_safe_name(name) for name in self._archive.namelist()}
        if PACKAGE_FILENAME not in self._names:
            raise BundleError("bundle is missing package.yaml")
        if CHECKSUM_FILENAME not in self._names:
            raise BundleError("bundle is missing checksums.sha256")
        self._package = yaml.safe_load(self._archive.read(PACKAGE_FILENAME)) or {}
        self._verify_package()

    @property
    def package(self) -> dict[str, Any]:
        """Return the validated package envelope."""
        return dict(self._package)

    @property
    def names(self) -> tuple[str, ...]:
        """Return sorted payload member names, excluding the checksum file."""
        return tuple(sorted(self._names - {CHECKSUM_FILENAME}))

    def read_bytes(self, name: str) -> bytes:
        """Read one verified member."""
        safe_name = _safe_name(name)
        if safe_name not in self._names or safe_name == CHECKSUM_FILENAME:
            raise BundleError(f"bundle member not found: {name}")
        return self._archive.read(safe_name)

    def read_yaml(self, name: str) -> dict[str, Any]:
        """Read one member as a YAML mapping."""
        value = yaml.safe_load(self.read_bytes(name))
        if not isinstance(value, dict):
            raise BundleError(f"bundle YAML member is not a mapping: {name}")
        return value

    def _verify_package(self) -> None:
        """Validate envelope fields, paths, and every declared checksum."""
        if self._package.get("format") != "rag-eval-bundle":
            raise BundleError("unsupported bundle format")
        if str(self._package.get("schema_version")) != SUPPORTED_SCHEMA_VERSION:
            raise BundleError(
                f"unsupported bundle schema: {self._package.get('schema_version')}"
            )
        for field_name in ("kind", "tool_version", "created_at", "resources"):
            if field_name not in self._package:
                raise BundleError(f"package.yaml is missing {field_name}")
        if not isinstance(self._package["resources"], dict):
            raise BundleError("package.yaml resources must be a mapping")
        checksums: dict[str, str] = {}
        for line in self._archive.read(CHECKSUM_FILENAME).decode("ascii").splitlines():
            digest, separator, name = line.partition("  ")
            if not separator or len(digest) != 64:
                raise BundleError("invalid checksum entry")
            checksums[_safe_name(name)] = digest
        expected_names = self._names - {CHECKSUM_FILENAME}
        if set(checksums) != expected_names:
            raise BundleError("checksums do not cover exactly the bundle members")
        for name, expected in checksums.items():
            actual = hashlib.sha256(self._archive.read(name)).hexdigest()
            if actual != expected:
                raise BundleError(f"checksum mismatch: {name}")


def _secret_placeholder(path: tuple[str, ...], secret: dict[str, Any]) -> str:
    """Create a stable human-readable placeholder for one SecretRef."""
    name = secret.get("name") or "_".join(path)
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_").upper()
    return f"${{RAG_EVAL_SECRET:{token or 'SECRET'}}}"


def redact_secret_refs(value: Any, *, _path: tuple[str, ...] = ()) -> Any:
    """Replace canonical SecretRef mappings with portable placeholders."""
    if isinstance(value, dict):
        if "secret_id" in value and set(value).issubset({"secret_id", "name"}):
            return _secret_placeholder(_path, value)
        return {
            key: redact_secret_refs(item, _path=(*_path, str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secret_refs(item, _path=_path) for item in value]
    return value


def resolve_secret_placeholders(
    value: Any,
    secrets: dict[str, str],
    *,
    _missing: list[str] | None = None,
) -> Any:
    """Resolve supplied placeholders and report, without exposing, omissions."""
    missing = _missing if _missing is not None else []
    if isinstance(value, str):
        match = _SECRET_PATTERN.fullmatch(value)
        if match is None:
            return value
        name = match.group(1)
        if name not in secrets:
            missing.append(name)
            return None
        return secrets[name]
    if isinstance(value, dict):
        return {
            key: resolved
            for key, item in value.items()
            if (
                resolved := resolve_secret_placeholders(item, secrets, _missing=missing)
            )
            is not None
        }
    if isinstance(value, list):
        return [
            resolved
            for item in value
            if (
                resolved := resolve_secret_placeholders(item, secrets, _missing=missing)
            )
            is not None
        ]
    return value

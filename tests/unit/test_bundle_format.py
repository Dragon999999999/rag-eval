"""Unit coverage for the portable `.rzip` envelope."""

import io
import zipfile

import pytest

from rag_eval.bundles import (
    BundleError,
    BundleReader,
    BundleWriter,
    redact_secret_refs,
    resolve_secret_placeholders,
)


def test_bundle_round_trip_verifies_envelope_and_checksums() -> None:
    """A writer produces a readable, checksummed package."""
    data = BundleWriter(kind="target").build()

    reader = BundleReader(data)

    assert reader.package["format"] == "rag-eval-bundle"
    assert reader.package["schema_version"] == "1"
    assert "package.yaml" in reader.names


def test_bundle_rejects_tampered_payload() -> None:
    """Checksum verification detects changed resource bytes."""
    writer = BundleWriter(kind="test")
    writer.add_text("tests/example/test.yaml", "name: Example\n")
    original = writer.build()
    tampered = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(original)) as source,
        zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as destination,
    ):
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "tests/example/test.yaml":
                payload = b"name: Tampered\n"
            destination.writestr(item, payload)

    with pytest.raises(BundleError):
        BundleReader(tampered.getvalue())


def test_secret_refs_round_trip_through_placeholders() -> None:
    """Secret references become named placeholders and missing values report."""
    value = {"auth": {"bearer_token": {"secret_id": "secret-1"}}}

    redacted = redact_secret_refs(value)
    resolved = resolve_secret_placeholders(
        redacted,
        {"AUTH_BEARER_TOKEN": "token"},
    )

    assert redacted["auth"]["bearer_token"] == ("${RAG_EVAL_SECRET:AUTH_BEARER_TOKEN}")
    assert resolved == {"auth": {"bearer_token": "token"}}

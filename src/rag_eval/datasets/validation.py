"""Dataset validation errors that are safe to report before target ingestion."""


class DatasetValidationError(ValueError):
    """A malformed or internally inconsistent native benchmark dataset."""

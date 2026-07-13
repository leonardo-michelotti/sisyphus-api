"""Contrato e identidade do artefato SQLite consumido pela API."""

from dataclasses import dataclass

SERVING_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class DatasetMetadata:
    schema_version: int
    dataset_version: str
    source_fetched_at: str
    pipeline_version: str
    parser_version: str
    run_id: str
    manifest_sha256: str
    source_commit: str

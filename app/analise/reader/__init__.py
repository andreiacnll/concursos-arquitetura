"""Architecture tender reader.

This package is intentionally separate from the historical analysis worker.
It classifies sources before extraction and only lets official procedure
documents enter the structured reader.
"""

from .architecture_reader import read_architecture_documents
from .spreadsheet_reader import (
    SPREADSHEET_EXTENSIONS,
    extract_spreadsheet_text,
    read_spreadsheet_document,
)
from .source_manifest import (
    ACCEPTED_READER_SOURCE_TYPES,
    SourceManifest,
    classify_source,
    create_source_manifest,
)

__all__ = [
    "ACCEPTED_READER_SOURCE_TYPES",
    "SourceManifest",
    "classify_source",
    "create_source_manifest",
    "read_architecture_documents",
    "SPREADSHEET_EXTENSIONS",
    "extract_spreadsheet_text",
    "read_spreadsheet_document",
]

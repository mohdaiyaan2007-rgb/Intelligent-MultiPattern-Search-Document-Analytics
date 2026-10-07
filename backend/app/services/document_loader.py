"""Decode supported document formats into original and searchable text."""

import csv
import io
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
SUPPORTED_FILE_TYPES = {".txt", ".md", ".csv"}


class DocumentLoadError(ValueError):
    """The uploaded filename or document contents are not supported."""


@dataclass(frozen=True)
class LoadedDocument:
    """Text extracted from a single supported document."""

    filename: str
    file_type: str
    original_text: str
    searchable_text: str


def _safe_filename(filename: str | None) -> str:
    """Keep only a display filename, never a client-supplied directory path."""
    if not filename:
        raise DocumentLoadError("A filename is required.")

    normalized_path = filename.replace("\\", "/")
    safe_name = PurePosixPath(normalized_path).name
    if safe_name in {"", ".", ".."}:
        raise DocumentLoadError("A valid filename is required.")
    return safe_name


def load_document(filename: str | None, content: bytes) -> LoadedDocument:
    """Decode a TXT, Markdown, or CSV file and prepare normalized search text."""
    safe_name = _safe_filename(filename)
    suffix = PurePosixPath(safe_name).suffix.lower()
    if suffix not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_FILE_TYPES))
        raise DocumentLoadError(
            f"Unsupported file type '{suffix or '(none)'}'. Supported types: {supported}."
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise DocumentLoadError("The file is larger than the 10 MiB upload limit.")

    try:
        original_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentLoadError("The file must contain valid UTF-8 text.") from error

    searchable_source = original_text
    if suffix == ".csv":
        try:
            rows = csv.reader(io.StringIO(original_text, newline=""), strict=True)
            searchable_source = "\n".join(" ".join(row) for row in rows)
        except csv.Error as error:
            raise DocumentLoadError("The CSV file could not be parsed.") from error

    # Preserve original_text for later display, and normalize only the search copy.
    searchable_text = " ".join(searchable_source.lower().split())
    return LoadedDocument(
        filename=safe_name,
        file_type=suffix[1:],
        original_text=original_text,
        searchable_text=searchable_text,
    )
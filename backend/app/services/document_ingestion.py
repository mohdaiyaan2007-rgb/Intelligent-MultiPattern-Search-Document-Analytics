"""Store ingested documents and their metadata."""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.document_loader import MAX_FILE_SIZE_BYTES, load_document
from backend.app.services.index_construction import add_document, remove_document

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS_DIRECTORY = PROJECT_ROOT / "data" / "documents"
METADATA_FILENAME = "metadata.json"

# Keep metadata updates from overlapping when multiple requests arrive together.
_metadata_lock = threading.Lock()


class DocumentIngestionError(ValueError):
	"""An uploaded document could not be accepted or stored."""


def _read_metadata(storage_directory: Path) -> dict[str, dict[str, Any]]:
	metadata_path = storage_directory / METADATA_FILENAME
	if not metadata_path.exists():
		return {}

	with metadata_path.open("r", encoding="utf-8") as metadata_file:
		return json.load(metadata_file)


def _write_metadata(storage_directory: Path, records: dict[str, dict[str, Any]]) -> None:
	metadata_path = storage_directory / METADATA_FILENAME
	temporary_path = storage_directory / f"{METADATA_FILENAME}.tmp"
	temporary_path.write_text(
		json.dumps(records, ensure_ascii=False, indent=2),
		encoding="utf-8",
	)
	temporary_path.replace(metadata_path)


def ingest_document(
	filename: str | None,
	content: bytes,
	storage_directory: Path = DOCUMENTS_DIRECTORY,
) -> dict[str, Any]:
	"""Validate, save, and index one uploaded document."""
	if len(content) > MAX_FILE_SIZE_BYTES:
		raise DocumentIngestionError("The file is larger than the 10 MiB upload limit.")

	try:
		loaded_document = load_document(filename, content)
	except ValueError as error:
		raise DocumentIngestionError(str(error)) from error

	storage_directory.mkdir(parents=True, exist_ok=True)
	document_id = uuid.uuid4().hex
	stored_filename = f"{document_id}.{loaded_document.file_type}"
	stored_path = storage_directory / stored_filename

	record: dict[str, Any] = {
		"document_id": document_id,
		"filename": loaded_document.filename,
		"file_type": loaded_document.file_type,
		"character_count": len(loaded_document.searchable_text),
		"word_count": len(loaded_document.searchable_text.split()),
		"indexed_at": datetime.now(timezone.utc).isoformat(),
		"stored_filename": stored_filename,
		"original_text": loaded_document.original_text,
		"searchable_text": loaded_document.searchable_text,
	}

	# The generated storage name prevents a client filename from becoming a path.
	stored_path.write_bytes(content)
	try:
		with _metadata_lock:
			records = _read_metadata(storage_directory)
			records[document_id] = record
			_write_metadata(storage_directory, records)
	except (OSError, json.JSONDecodeError) as error:
		stored_path.unlink(missing_ok=True)
		raise DocumentIngestionError("Document metadata could not be saved.") from error

	add_document(document_id, loaded_document.searchable_text)
	return record


def list_documents(storage_directory: Path = DOCUMENTS_DIRECTORY) -> list[dict[str, Any]]:
	"""Return stored document records, newest first."""
	with _metadata_lock:
		records = _read_metadata(storage_directory)
	return sorted(records.values(), key=lambda record: record["indexed_at"], reverse=True)


def delete_document(document_id: str, storage_directory: Path = DOCUMENTS_DIRECTORY) -> bool:
	"""Delete a stored document and its metadata; return False if it is unknown."""
	with _metadata_lock:
		records = _read_metadata(storage_directory)
		record = records.get(document_id)
		if record is None:
			return False

		(storage_directory / record["stored_filename"]).unlink(missing_ok=True)
		del records[document_id]
		_write_metadata(storage_directory, records)
	remove_document(document_id)
	return True
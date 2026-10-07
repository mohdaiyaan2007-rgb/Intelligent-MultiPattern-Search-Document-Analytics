"""Build and maintain an in-memory inverted index for ingested documents."""

import re
import threading
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_index_lock = threading.RLock()
_inverted_index: dict[str, dict[str, list[int]]] = {}
_indexed_document_ids: set[str] = set()


def _get_words(text: str) -> list[str]:
	"""Lowercase text and split it into words at punctuation and whitespace."""
	return [word for word, _, _ in tokenize_with_spans(text)]


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
	"""Return normalized words with their character start and end offsets."""
	return [
		(match.group().lower(), match.start(), match.end())
		for match in _WORD_PATTERN.finditer(text)
	]


def _remove_document_locked(document_id: str) -> None:
	"""Remove one document's postings while the index lock is held."""
	_indexed_document_ids.discard(document_id)
	for term in list(_inverted_index):
		_inverted_index[term].pop(document_id, None)
		if not _inverted_index[term]:
			del _inverted_index[term]


def add_document(document_id: str, searchable_text: str) -> None:
	"""Add or replace a document's word-to-position postings."""
	words = _get_words(searchable_text)

	with _index_lock:
		# Remove old postings first so retrying an upload cannot duplicate them.
		_remove_document_locked(document_id)
		if not words:
			return

		# Each term points to its positions in this document's word sequence.
		for position, word in enumerate(words):
			positions_by_document = _inverted_index.setdefault(word, {})
			positions_by_document.setdefault(document_id, []).append(position)
		_indexed_document_ids.add(document_id)


def remove_document(document_id: str) -> None:
	"""Remove all terms and positions belonging to one document."""
	with _index_lock:
		_remove_document_locked(document_id)


def rebuild_index(
	documents: Iterable[Mapping[str, Any]] | None = None,
	storage_directory: Path | None = None,
) -> dict[str, int]:
	"""Replace the in-memory index using stored documents or supplied records."""
	if documents is None:
		# Import here to avoid a module cycle with the ingestion service.
		from backend.app.services.document_ingestion import list_documents

		documents = (
			list_documents(storage_directory)
			if storage_directory is not None
			else list_documents()
		)

	rebuilt_index: dict[str, dict[str, list[int]]] = {}
	rebuilt_document_ids: set[str] = set()
	seen_document_ids: set[str] = set()

	for document in documents:
		document_id = document.get("document_id")
		if not isinstance(document_id, str) or document_id in seen_document_ids:
			continue
		seen_document_ids.add(document_id)

		words = _get_words(str(document.get("searchable_text", "")))
		if not words:
			continue

		# Building fresh dictionaries makes repeated rebuilds naturally idempotent.
		for position, word in enumerate(words):
			positions_by_document = rebuilt_index.setdefault(word, {})
			positions_by_document.setdefault(document_id, []).append(position)
		rebuilt_document_ids.add(document_id)

	with _index_lock:
		global _inverted_index, _indexed_document_ids
		_inverted_index = rebuilt_index
		_indexed_document_ids = rebuilt_document_ids

	return get_index_stats()


def get_postings(term: str) -> dict[str, list[int]]:
	"""Return a copy of the postings for a single normalized word."""
	words = _get_words(term)
	if len(words) != 1:
		return {}

	with _index_lock:
		return {
			document_id: positions.copy()
			for document_id, positions in _inverted_index.get(words[0], {}).items()
		}


def get_indexed_document_ids() -> set[str]:
	"""Return a snapshot of the IDs that currently have indexed words."""
	with _index_lock:
		return _indexed_document_ids.copy()


def get_index_terms() -> set[str]:
	"""Return a snapshot of all terms currently stored in the inverted index."""
	with _index_lock:
		return set(_inverted_index)


def get_index_snapshot() -> dict[str, dict[str, list[int]]]:
	"""Return a deep copy of term postings for read-only collection analysis."""
	with _index_lock:
		return {
			term: {
				document_id: positions.copy()
				for document_id, positions in documents_by_term.items()
			}
			for term, documents_by_term in _inverted_index.items()
		}


def get_index_stats() -> dict[str, int]:
	"""Return counts derived from the current index, not estimates."""
	with _index_lock:
		total_occurrences = sum(
			len(positions)
			for documents_by_term in _inverted_index.values()
			for positions in documents_by_term.values()
		)
		return {
			"total_indexed_documents": len(_indexed_document_ids),
			"total_unique_terms": len(_inverted_index),
			"total_term_occurrences": total_occurrences,
		}
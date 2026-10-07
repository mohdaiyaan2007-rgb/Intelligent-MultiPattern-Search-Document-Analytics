"""Calculate collection, document, and term statistics from the inverted index."""

from pathlib import Path
from typing import Any

from backend.app.services.document_ingestion import list_documents
from backend.app.services.index_construction import (
	get_index_snapshot,
	get_indexed_document_ids,
)

MOST_FREQUENT_TERMS_PER_DOCUMENT = 5


def _collect_analytics(
	storage_directory: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	"""Aggregate per-document and per-term counts from indexed token positions."""
	documents = list_documents(storage_directory) if storage_directory is not None else list_documents()
	indexed_ids = get_indexed_document_ids()
	document_records = {
		document["document_id"]: document
		for document in documents
		if document.get("document_id") in indexed_ids
	}
	per_document_frequencies: dict[str, dict[str, int]] = {
		document_id: {} for document_id in document_records
	}
	document_stats: dict[str, dict[str, Any]] = {
		document_id: {
			"document_id": document_id,
			"filename": document["filename"],
			"word_count": 0,
			"document_length": 0,
			"unique_term_count": 0,
			"most_frequent_terms": [],
		}
		for document_id, document in document_records.items()
	}
	term_stats: list[dict[str, Any]] = []

	# Index postings are word positions: their count gives term frequency without
	# rescanning and retokenizing every document's text.
	for term, postings in get_index_snapshot().items():
		valid_postings = {
			document_id: positions
			for document_id, positions in postings.items()
			if document_id in document_records
		}
		if not valid_postings:
			continue

		term_frequency = sum(len(positions) for positions in valid_postings.values())
		# Document frequency counts distinct documents with at least one posting.
		term_stats.append(
			{
				"term": term,
				"frequency": term_frequency,
				"document_frequency": len(valid_postings),
			}
		)
		for document_id, positions in valid_postings.items():
			count = len(positions)
			per_document_frequencies[document_id][term] = count
			document_stats[document_id]["word_count"] += count
			document_stats[document_id]["document_length"] += count
			document_stats[document_id]["unique_term_count"] += 1

	for document_id, stats in document_stats.items():
		frequencies = per_document_frequencies[document_id]
		stats["most_frequent_terms"] = [
			{"term": term, "frequency": frequency}
			for term, frequency in sorted(
				frequencies.items(), key=lambda item: (-item[1], item[0])
			)[:MOST_FREQUENT_TERMS_PER_DOCUMENT]
		]

	document_results = sorted(
		document_stats.values(),
		key=lambda stats: (stats["filename"].casefold(), stats["document_id"]),
	)
	term_results = sorted(term_stats, key=lambda stats: (-stats["frequency"], stats["term"]))
	return document_results, term_results


def get_collection_summary(storage_directory: Path | None = None) -> dict[str, int | float]:
	"""Return document counts and token-length measurements for the collection."""
	documents, terms = _collect_analytics(storage_directory)
	total_words = sum(document["word_count"] for document in documents)
	total_documents = len(documents)
	document_lengths = [document["document_length"] for document in documents]

	# Average, shortest, and longest lengths use only documents represented in the index.
	return {
		"total_documents": total_documents,
		"total_words": total_words,
		"unique_terms": len(terms),
		"average_document_length": round(total_words / total_documents, 2)
		if total_documents
		else 0.0,
		"shortest_document_length": min(document_lengths) if document_lengths else 0,
		"longest_document_length": max(document_lengths) if document_lengths else 0,
	}


def get_document_analytics(storage_directory: Path | None = None) -> list[dict[str, Any]]:
	"""Return deterministic per-document word and unique-term statistics."""
	documents, _ = _collect_analytics(storage_directory)
	return documents


def get_term_analytics(
	limit: int = 10,
	storage_directory: Path | None = None,
) -> list[dict[str, Any]]:
	"""Return the most frequent terms, alphabetically breaking frequency ties."""
	_, terms = _collect_analytics(storage_directory)
	return terms[:max(0, limit)]
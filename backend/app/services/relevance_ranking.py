"""Rank keyword-search results using transparent inverted-index signals."""

from pathlib import Path
from typing import Any

from backend.app.services.document_ingestion import list_documents
from backend.app.services.index_construction import (
	get_indexed_document_ids,
	get_postings,
	tokenize_with_spans,
)
from backend.app.services.phrase_wildcard_search import search_phrase

SNIPPET_CONTEXT_CHARS = 40
PHRASE_MATCH_WEIGHT = 2


def _make_snippet(text: str, start: int, end: int) -> str:
	"""Return a short excerpt surrounding a character range."""
	left = max(0, start - SNIPPET_CONTEXT_CHARS)
	right = min(len(text), end + SNIPPET_CONTEXT_CHARS)
	snippet = text[left:right]
	if left:
		snippet = "..." + snippet
	if right < len(text):
		snippet += "..."
	return snippet


def rank_search_results(
	query: str,
	storage_directory: Path | None = None,
) -> dict[str, Any]:
	"""Find query-term candidates and order them by a simple relevance score."""
	query_words = [word for word, _, _ in tokenize_with_spans(query)]
	query_terms = list(dict.fromkeys(query_words))
	if not query_terms:
		return {
			"query": query,
			"documents_searched": 0,
			"total_matches": 0,
			"results": [],
		}

	# The inverted index provides only documents that contain at least one query term.
	postings_by_term = {term: get_postings(term) for term in query_terms}
	candidate_document_ids: set[str] = set()
	for postings in postings_by_term.values():
		candidate_document_ids.update(postings)
	candidate_document_ids.intersection_update(get_indexed_document_ids())

	if not candidate_document_ids:
		return {
			"query": query,
			"documents_searched": 0,
			"total_matches": 0,
			"results": [],
		}

	documents = list_documents(storage_directory) if storage_directory is not None else list_documents()
	documents_by_id = {
		document["document_id"]: document
		for document in documents
		if document.get("document_id") in candidate_document_ids
	}
	candidate_document_ids.intersection_update(documents_by_id)

	# Exact consecutive query phrases receive a small, explicit additional signal.
	phrase_result = (
		search_phrase(query, storage_directory)
		if len(query_words) > 1
		else {"results": []}
	)
	phrase_counts = {
		result["document_id"]: result["match_count"]
		for result in phrase_result["results"]
	}
	ranked_results: list[dict[str, Any]] = []
	total_matches = 0

	for document_id in candidate_document_ids:
		document = documents_by_id[document_id]
		match_counts = {
			term: len(postings_by_term[term].get(document_id, []))
			for term in query_terms
			if postings_by_term[term].get(document_id)
		}
		term_frequency = sum(match_counts.values())
		matched_term_count = len(match_counts)
		phrase_match_count = phrase_counts.get(document_id, 0)

		# Score = total term frequency + distinct query terms found + 2 per exact phrase.
		# Frequent terms matter because repeated evidence raises the document's score.
		relevance_score = (
			term_frequency
			+ matched_term_count
			+ PHRASE_MATCH_WEIGHT * phrase_match_count
		)

		searchable_text = str(document.get("searchable_text", ""))
		phrase_result_for_document = next(
			(
				result
				for result in phrase_result["results"]
				if result["document_id"] == document_id
			),
			None,
		)
		if phrase_result_for_document:
			snippet = phrase_result_for_document["snippets"][0]
		else:
			word_spans = tokenize_with_spans(searchable_text)
			first_position = min(
				position
				for term in match_counts
				for position in postings_by_term[term][document_id]
			)
			start, end = word_spans[first_position][1:]
			snippet = _make_snippet(searchable_text, start, end)

		ranked_results.append(
			{
				"document_id": document_id,
				"filename": document["filename"],
				"relevance_score": relevance_score,
				"matched_terms": list(match_counts),
				"match_counts": match_counts,
				"term_frequency": term_frequency,
				"phrase_match_count": phrase_match_count,
				"snippet": snippet,
			}
		)
		total_matches += term_frequency

	# Filename and ID make equal scores sort in a repeatable order.
	ranked_results.sort(
		key=lambda result: (
			-result["relevance_score"],
			result["filename"].casefold(),
			result["document_id"],
		)
	)
	return {
		"query": query,
		"documents_searched": len(candidate_document_ids),
		"total_matches": total_matches,
		"results": ranked_results,
	}
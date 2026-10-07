"""Search indexed documents for exact phrases and simple word wildcards."""

from pathlib import Path
from typing import Any

from backend.app.services.document_ingestion import list_documents
from backend.app.services.index_construction import (
	get_index_terms,
	get_indexed_document_ids,
	get_postings,
	tokenize_with_spans,
)

SNIPPET_CONTEXT_CHARS = 40


class WildcardPatternError(ValueError):
	"""The wildcard pattern is outside the supported simple syntax."""


def _indexed_documents(storage_directory: Path | None) -> list[dict[str, Any]]:
	"""Pair stored document text with the IDs currently present in the index."""
	documents = list_documents(storage_directory) if storage_directory is not None else list_documents()
	indexed_ids = get_indexed_document_ids()
	return [document for document in documents if document.get("document_id") in indexed_ids]


def _make_snippet(text: str, start: int, end: int) -> str:
	"""Return a short searchable-text excerpt around a character range."""
	left = max(0, start - SNIPPET_CONTEXT_CHARS)
	right = min(len(text), end + SNIPPET_CONTEXT_CHARS)
	snippet = text[left:right]
	if left:
		snippet = "..." + snippet
	if right < len(text):
		snippet += "..."
	return snippet


def search_phrase(phrase: str, storage_directory: Path | None = None) -> dict[str, Any]:
	"""Find exact consecutive word sequences using inverted-index positions."""
	phrase_words = [word for word, _, _ in tokenize_with_spans(phrase)]
	documents = _indexed_documents(storage_directory)
	results: list[dict[str, Any]] = []
	total_matches = 0

	if phrase_words:
		# The first word's postings narrow the candidate documents via the index.
		postings_by_word = [get_postings(word) for word in phrase_words]
		candidate_document_ids = set(postings_by_word[0])
		for postings in postings_by_word[1:]:
			candidate_document_ids.intersection_update(postings)

		for document in documents:
			document_id = document["document_id"]
			if document_id not in candidate_document_ids:
				continue

			# Every next word must have a posting exactly one position later.
			positions_by_word = [
				set(postings.get(document_id, [])) for postings in postings_by_word
			]
			start_positions = [
				start
				for start in sorted(positions_by_word[0])
				if all(
					start + offset in positions
					for offset, positions in enumerate(positions_by_word[1:], start=1)
				)
			]
			if not start_positions:
				continue

			searchable_text = str(document.get("searchable_text", ""))
			word_spans = tokenize_with_spans(searchable_text)
			clean_phrase = phrase.strip()
			results.append(
				{
					"document_id": document_id,
					"filename": document["filename"],
					"matched_phrase": clean_phrase,
					"match_count": len(start_positions),
					"positions": start_positions,
					"snippets": [
						_make_snippet(
							searchable_text,
							word_spans[start][1],
							word_spans[start + len(phrase_words) - 1][2],
						)
						for start in start_positions
					],
				}
			)
			total_matches += len(start_positions)

	return {
		"phrase": phrase,
		"documents_searched": len(documents),
		"total_matches": total_matches,
		"results": results,
	}


def _parse_wildcard(pattern: str) -> tuple[str, str] | None:
	"""Return (direction, literal) for a supported leading or trailing star."""
	clean_pattern = " ".join(pattern.split()).lower()
	if not clean_pattern or clean_pattern == "*":
		return None
	if clean_pattern.count("*") != 1:
		raise WildcardPatternError("Use one '*' at the beginning or end of a word.")

	if clean_pattern.startswith("*"):
		direction = "suffix"
		literal = clean_pattern[1:].strip()
	elif clean_pattern.endswith("*"):
		direction = "prefix"
		literal = clean_pattern[:-1].strip()
	else:
		raise WildcardPatternError("The '*' wildcard is supported only at the beginning or end.")

	words = [word for word, _, _ in tokenize_with_spans(literal)]
	if len(words) != 1 or words[0] != literal:
		raise WildcardPatternError("The non-wildcard part must be one word.")
	return direction, literal


def search_wildcard(pattern: str, storage_directory: Path | None = None) -> dict[str, Any]:
	"""Expand one prefix/suffix wildcard against the current index vocabulary."""
	parsed_pattern = _parse_wildcard(pattern)
	documents = _indexed_documents(storage_directory)
	indexed_document_ids = {document["document_id"] for document in documents}
	positions_by_document: dict[str, dict[str, list[int]]] = {}
	matched_terms: list[str] = []

	if parsed_pattern is not None:
		direction, literal = parsed_pattern
		# A trailing star checks prefixes; a leading star checks word suffixes.
		matched_terms = sorted(
			term
			for term in get_index_terms()
			if (term.startswith(literal) if direction == "prefix" else term.endswith(literal))
		)
		for term in matched_terms:
			for document_id, positions in get_postings(term).items():
				if document_id in indexed_document_ids:
					positions_by_document.setdefault(document_id, {})[term] = positions

	results: list[dict[str, Any]] = []
	total_matches = 0
	for document in documents:
		document_id = document["document_id"]
		term_positions = positions_by_document.get(document_id)
		if not term_positions:
			continue

		searchable_text = str(document.get("searchable_text", ""))
		word_spans = tokenize_with_spans(searchable_text)
		matches = []
		for term, positions in term_positions.items():
			matches.append(
				{
					"matched_term": term,
					"match_count": len(positions),
					"positions": positions,
					"snippets": [
						_make_snippet(searchable_text, word_spans[position][1], word_spans[position][2])
						for position in positions
					],
				}
			)
			total_matches += len(positions)

		results.append(
			{
				"document_id": document_id,
				"filename": document["filename"],
				"matches": matches,
			}
		)

	return {
		"pattern": pattern,
		"documents_searched": len(documents),
		"total_matches": total_matches,
		"matched_terms": matched_terms,
		"results": results,
	}
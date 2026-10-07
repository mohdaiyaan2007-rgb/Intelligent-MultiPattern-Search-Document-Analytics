"""Search indexed document text for many patterns with Aho-Corasick."""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.services.document_ingestion import list_documents
from backend.app.services.index_construction import get_indexed_document_ids

SNIPPET_CONTEXT_CHARS = 40


@dataclass
class _TrieNode:
	"""One trie state, with links used while scanning document text."""

	children: dict[str, "_TrieNode"] = field(default_factory=dict)
	failure: "_TrieNode | None" = None
	patterns: list[str] = field(default_factory=list)
	output_link: "_TrieNode | None" = None


class AhoCorasickMatcher:
	"""Match many lowercase patterns in one pass over a text string."""

	def __init__(self, patterns: Iterable[str]) -> None:
		normalized_patterns = (" ".join(pattern.split()).lower() for pattern in patterns)
		self.patterns = list(dict.fromkeys(pattern for pattern in normalized_patterns if pattern))
		self.root = _TrieNode()
		self.root.failure = self.root
		self._build_trie()
		self._build_failure_links()

	def _build_trie(self) -> None:
		"""Insert each pattern into a shared prefix tree of characters."""
		for pattern in self.patterns:
			current = self.root
			for character in pattern:
				current = current.children.setdefault(character, _TrieNode())
			current.patterns.append(pattern)

	def _build_failure_links(self) -> None:
		"""Link a failed path to its longest suffix that is also a trie prefix."""
		pending_nodes: deque[_TrieNode] = deque()
		for child in self.root.children.values():
			child.failure = self.root
			pending_nodes.append(child)

		while pending_nodes:
			parent = pending_nodes.popleft()
			for character, child in parent.children.items():
				fallback = parent.failure or self.root
				while fallback is not self.root and character not in fallback.children:
					fallback = fallback.failure or self.root

				child.failure = fallback.children.get(character, self.root)
				failure_target = child.failure
				# An output link jumps to the nearest suffix state that ends a pattern.
				if failure_target.patterns:
					child.output_link = failure_target
				else:
					child.output_link = failure_target.output_link
				pending_nodes.append(child)

	def find_matches(self, text: str) -> dict[str, list[int]]:
		"""Return every pattern's zero-based character start positions."""
		matches = {pattern: [] for pattern in self.patterns}
		current = self.root

		# One shared scan avoids rescanning the document separately for every pattern.
		for end_position, character in enumerate(text.lower()):
			while current is not self.root and character not in current.children:
				current = current.failure or self.root
			current = current.children.get(character, self.root)

			# Check this state and its output links for patterns ending here.
			output_state: _TrieNode | None = current
			while output_state is not None:
				for pattern in output_state.patterns:
					start_position = end_position - len(pattern) + 1
					matches[pattern].append(start_position)
				output_state = output_state.output_link

		return matches


def _prepare_patterns(patterns: Iterable[str]) -> dict[str, str]:
	"""Normalize patterns and retain the first spelling for the response."""
	prepared: dict[str, str] = {}
	for pattern in patterns:
		cleaned_pattern = " ".join(pattern.split())
		normalized_pattern = cleaned_pattern.lower()
		if normalized_pattern and normalized_pattern not in prepared:
			prepared[normalized_pattern] = cleaned_pattern
	return prepared


def _make_snippet(text: str, start: int, end: int) -> str:
	"""Return a short context window around one match in searchable text."""
	left = max(0, start - SNIPPET_CONTEXT_CHARS)
	right = min(len(text), end + SNIPPET_CONTEXT_CHARS)
	snippet = text[left:right]
	if left:
		snippet = "..." + snippet
	if right < len(text):
		snippet += "..."
	return snippet


def search_multiple_patterns(
	patterns: Iterable[str],
	storage_directory: Path | None = None,
) -> dict[str, Any]:
	"""Search all currently indexed documents and group matches by document."""
	prepared_patterns = _prepare_patterns(patterns)
	documents = list_documents(storage_directory) if storage_directory else list_documents()
	indexed_document_ids = get_indexed_document_ids()
	indexed_documents = [
		document
		for document in documents
		if document.get("document_id") in indexed_document_ids
	]
	matcher = AhoCorasickMatcher(prepared_patterns)
	results: list[dict[str, Any]] = []
	total_matches = 0

	for document in indexed_documents:
		searchable_text = str(document.get("searchable_text", ""))
		positions_by_pattern = matcher.find_matches(searchable_text)
		document_matches = []

		for normalized_pattern, display_pattern in prepared_patterns.items():
			positions = positions_by_pattern[normalized_pattern]
			if not positions:
				continue

			document_matches.append(
				{
					"matched_pattern": display_pattern,
					"match_count": len(positions),
					"positions": positions,
					"snippets": [
						_make_snippet(
							searchable_text,
							position,
							position + len(normalized_pattern),
						)
						for position in positions
					],
				}
			)
			total_matches += len(positions)

		if document_matches:
			results.append(
				{
					"document_id": document["document_id"],
					"filename": document["filename"],
					"matches": document_matches,
				}
			)

	return {
		"searched_patterns": list(prepared_patterns.values()),
		"documents_searched": len(indexed_documents),
		"total_matches": total_matches,
		"results": results,
	}
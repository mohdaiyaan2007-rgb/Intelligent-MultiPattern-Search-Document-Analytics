"""Tests for exact phrase and simple wildcard search."""

import tempfile
import unittest
from pathlib import Path

from backend.app.services.document_ingestion import ingest_document
from backend.app.services.index_construction import rebuild_index
from backend.app.services.phrase_wildcard_search import (
	WildcardPatternError,
	search_phrase,
	search_wildcard,
)


class PhraseWildcardSearchTests(unittest.TestCase):
	def setUp(self) -> None:
		rebuild_index([])
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.storage_directory = Path(self.temporary_directory.name)

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()
		rebuild_index([])

	def _ingest(self, filename: str, text: str) -> dict[str, object]:
		return ingest_document(filename, text.encode("utf-8"), self.storage_directory)

	def test_finds_exact_phrase_and_returns_positions_and_snippets(self) -> None:
		self._ingest("machine.txt", "Machine learning supports machine learning tools.")

		response = search_phrase("machine learning", self.storage_directory)

		self.assertEqual(response["total_matches"], 2)
		self.assertEqual(response["results"][0]["matched_phrase"], "machine learning")
		self.assertEqual(response["results"][0]["positions"], [0, 3])
		self.assertIn("machine learning supports", response["results"][0]["snippets"][0])

	def test_phrase_not_found_returns_no_results(self) -> None:
		self._ingest("order.txt", "python database")

		response = search_phrase("database python", self.storage_directory)

		self.assertEqual(response["documents_searched"], 1)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_multiple_words_must_be_consecutive_and_in_order(self) -> None:
		self._ingest("sequence.txt", "python uses a database for search")

		found = search_phrase("python uses a database", self.storage_directory)
		not_found = search_phrase("python database", self.storage_directory)

		self.assertEqual(found["total_matches"], 1)
		self.assertEqual(found["results"][0]["positions"], [0])
		self.assertEqual(not_found["total_matches"], 0)

	def test_repeated_words_use_consecutive_index_positions(self) -> None:
		self._ingest("repeat.txt", "data data data")

		response = search_phrase("data data", self.storage_directory)

		self.assertEqual(response["total_matches"], 2)
		self.assertEqual(response["results"][0]["positions"], [0, 1])

	def test_phrase_matching_is_case_insensitive(self) -> None:
		self._ingest("case.txt", "MACHINE learning is useful")

		response = search_phrase("Machine LEARNING", self.storage_directory)

		self.assertEqual(response["total_matches"], 1)

	def test_single_word_phrase_is_supported(self) -> None:
		self._ingest("single.txt", "python database python")

		response = search_phrase("PYTHON", self.storage_directory)

		self.assertEqual(response["total_matches"], 2)
		self.assertEqual(response["results"][0]["positions"], [0, 2])

	def test_empty_phrase_returns_no_matches(self) -> None:
		self._ingest("empty-phrase.txt", "python database")

		response = search_phrase("   ", self.storage_directory)

		self.assertEqual(response["phrase"], "   ")
		self.assertEqual(response["documents_searched"], 1)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_prefix_wildcard_finds_terms_starting_with_literal(self) -> None:
		self._ingest("prefix.txt", "python pythonic database")

		response = search_wildcard("PYTH*", self.storage_directory)

		self.assertEqual(response["matched_terms"], ["python", "pythonic"])
		self.assertEqual(response["total_matches"], 2)
		self.assertEqual(
			{
				match["matched_term"]: match["positions"]
				for match in response["results"][0]["matches"]
			},
			{"python": [0], "pythonic": [1]},
		)

	def test_suffix_wildcard_finds_terms_ending_with_literal(self) -> None:
		self._ingest("suffix.txt", "database codebase base datacenter")

		response = search_wildcard("*BASE", self.storage_directory)

		self.assertEqual(response["matched_terms"], ["base", "codebase", "database"])
		self.assertEqual(response["total_matches"], 3)

	def test_wildcard_without_matches_returns_empty_results(self) -> None:
		self._ingest("no-wildcard-match.txt", "python database")

		response = search_wildcard("machine*", self.storage_directory)

		self.assertEqual(response["matched_terms"], [])
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_empty_wildcard_does_not_match_every_term(self) -> None:
		self._ingest("empty-wildcard.txt", "python database")

		for pattern in ("", "*"):
			response = search_wildcard(pattern, self.storage_directory)
			self.assertEqual(response["matched_terms"], [])
			self.assertEqual(response["total_matches"], 0)

	def test_search_groups_matches_across_multiple_documents(self) -> None:
		first = self._ingest("first.txt", "machine learning")
		second = self._ingest("second.txt", "machine learning and machine learning")

		response = search_phrase("machine learning", self.storage_directory)

		self.assertEqual(response["documents_searched"], 2)
		self.assertEqual(response["total_matches"], 3)
		self.assertEqual(
			{result["document_id"] for result in response["results"]},
			{first["document_id"], second["document_id"]},
		)

	def test_wildcard_requires_one_edge_asterisk(self) -> None:
		with self.assertRaisesRegex(WildcardPatternError, "beginning or end"):
			search_wildcard("ma*ne", self.storage_directory)


if __name__ == "__main__":
	unittest.main()
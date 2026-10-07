"""Tests for Aho-Corasick multi-pattern search."""

import tempfile
import unittest
from pathlib import Path

from backend.app.services.document_ingestion import ingest_document
from backend.app.services.index_construction import rebuild_index
from backend.app.services.multi_pattern_search import (
	AhoCorasickMatcher,
	search_multiple_patterns,
)


class MultiPatternSearchTests(unittest.TestCase):
	def setUp(self) -> None:
		rebuild_index([])
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.storage_directory = Path(self.temporary_directory.name)

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()
		rebuild_index([])

	def _ingest(self, filename: str, text: str) -> dict[str, object]:
		return ingest_document(filename, text.encode("utf-8"), self.storage_directory)

	def test_searches_for_one_pattern_and_returns_positions_and_snippet(self) -> None:
		document = self._ingest("python.txt", "Python makes Python scripts readable.")

		response = search_multiple_patterns(["python"], self.storage_directory)

		self.assertEqual(response["searched_patterns"], ["python"])
		self.assertEqual(response["documents_searched"], 1)
		self.assertEqual(response["total_matches"], 2)
		match = response["results"][0]["matches"][0]
		self.assertEqual(match["matched_pattern"], "python")
		self.assertEqual(match["match_count"], 2)
		self.assertEqual(match["positions"], [0, 13])
		self.assertEqual(response["results"][0]["document_id"], document["document_id"])
		self.assertIn("python makes", match["snippets"][0])

	def test_searches_for_multiple_patterns_in_one_document(self) -> None:
		self._ingest("notes.md", "Python uses a database for machine learning projects.")

		response = search_multiple_patterns(
			["python", "database", "machine learning"],
			self.storage_directory,
		)

		self.assertEqual(response["total_matches"], 3)
		self.assertEqual(
			[match["matched_pattern"] for match in response["results"][0]["matches"]],
			["python", "database", "machine learning"],
		)

	def test_overlapping_patterns_are_both_reported(self) -> None:
		self._ingest("overlap.txt", "ushers")

		response = search_multiple_patterns(["he", "she", "hers"], self.storage_directory)
		matches = {
			match["matched_pattern"]: match["positions"]
			for match in response["results"][0]["matches"]
		}

		self.assertEqual(matches, {"he": [2], "she": [1], "hers": [2]})
		self.assertEqual(response["total_matches"], 3)

	def test_repeated_patterns_create_only_one_pattern_definition(self) -> None:
		self._ingest("repeat.txt", "python supports many patterns")

		response = search_multiple_patterns(
			["Python", "python", " PYTHON "],
			self.storage_directory,
		)

		self.assertEqual(response["searched_patterns"], ["Python"])
		self.assertEqual(response["total_matches"], 1)

	def test_matcher_is_case_insensitive(self) -> None:
		matcher = AhoCorasickMatcher(["Python", "", "   ", " PYTHON "])

		self.assertEqual(matcher.patterns, ["python"])
		self.assertEqual(matcher.find_matches("PYTHON and python"), {"python": [0, 11]})

	def test_patterns_not_found_return_no_results(self) -> None:
		self._ingest("short.txt", "cat")

		response = search_multiple_patterns(["dog", "elephant"], self.storage_directory)

		self.assertEqual(response["documents_searched"], 1)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_empty_patterns_are_ignored(self) -> None:
		self._ingest("empty-query.txt", "some searchable text")

		response = search_multiple_patterns(["", "   "], self.storage_directory)

		self.assertEqual(response["searched_patterns"], [])
		self.assertEqual(response["documents_searched"], 1)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_results_are_grouped_across_multiple_documents(self) -> None:
		first = self._ingest("first.txt", "database systems")
		second = self._ingest("second.txt", "database engines")

		response = search_multiple_patterns(["database"], self.storage_directory)

		self.assertEqual(response["documents_searched"], 2)
		self.assertEqual(response["total_matches"], 2)
		self.assertEqual(
			{result["document_id"] for result in response["results"]},
			{first["document_id"], second["document_id"]},
		)


if __name__ == "__main__":
	unittest.main()
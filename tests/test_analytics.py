"""Tests for collection, per-document, and term analytics."""

import tempfile
import unittest
from pathlib import Path

from backend.app.services.analytics import (
	get_collection_summary,
	get_document_analytics,
	get_term_analytics,
)
from backend.app.services.document_ingestion import delete_document, ingest_document
from backend.app.services.index_construction import rebuild_index


class DocumentAnalyticsTests(unittest.TestCase):
	def setUp(self) -> None:
		rebuild_index([])
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.storage_directory = Path(self.temporary_directory.name)

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()
		rebuild_index([])

	def _ingest(self, filename: str, text: str) -> dict[str, object]:
		return ingest_document(filename, text.encode("utf-8"), self.storage_directory)

	def test_empty_collection_has_zero_metrics(self) -> None:
		self.assertEqual(
			get_collection_summary(self.storage_directory),
			{
				"total_documents": 0,
				"total_words": 0,
				"unique_terms": 0,
				"average_document_length": 0.0,
				"shortest_document_length": 0,
				"longest_document_length": 0,
			},
		)
		self.assertEqual(get_document_analytics(self.storage_directory), [])
		self.assertEqual(get_term_analytics(storage_directory=self.storage_directory), [])

	def test_collection_metrics_cover_multiple_documents(self) -> None:
		self._ingest("zeta.txt", "pear pear plum")
		self._ingest("alpha.md", "plum peach")

		self.assertEqual(
			get_collection_summary(self.storage_directory),
			{
				"total_documents": 2,
				"total_words": 5,
				"unique_terms": 3,
				"average_document_length": 2.5,
				"shortest_document_length": 2,
				"longest_document_length": 3,
			},
		)

	def test_per_document_counts_and_frequent_terms_are_consistent(self) -> None:
		self._ingest("zeta.txt", "pear pear plum")
		self._ingest("alpha.md", "plum peach")

		documents = get_document_analytics(self.storage_directory)

		self.assertEqual([document["filename"] for document in documents], ["alpha.md", "zeta.txt"])
		self.assertEqual(
			{
				key: documents[1][key]
				for key in ("word_count", "document_length", "unique_term_count")
			},
			{"word_count": 3, "document_length": 3, "unique_term_count": 2},
		)
		self.assertEqual(
			documents[1]["most_frequent_terms"],
			[
				{"term": "pear", "frequency": 2},
				{"term": "plum", "frequency": 1},
			],
		)

	def test_term_frequency_and_document_frequency_count_repeats_correctly(self) -> None:
		self._ingest("one.txt", "pear pear plum")
		self._ingest("two.txt", "plum peach")

		terms = get_term_analytics(limit=3, storage_directory=self.storage_directory)

		self.assertEqual(
			terms,
			[
				{"term": "pear", "frequency": 2, "document_frequency": 1},
				{"term": "plum", "frequency": 2, "document_frequency": 2},
				{"term": "peach", "frequency": 1, "document_frequency": 1},
			],
		)

	def test_term_frequency_ties_are_sorted_alphabetically(self) -> None:
		self._ingest("terms.txt", "zebra apple")

		terms = get_term_analytics(storage_directory=self.storage_directory)

		self.assertEqual([term["term"] for term in terms], ["apple", "zebra"])

	def test_analytics_update_after_adding_a_document(self) -> None:
		self._ingest("one.txt", "python python")
		self._ingest("two.txt", "python database")

		summary = get_collection_summary(self.storage_directory)
		terms = get_term_analytics(storage_directory=self.storage_directory)

		self.assertEqual(summary["total_documents"], 2)
		self.assertEqual(summary["total_words"], 4)
		self.assertEqual(terms[0], {"term": "python", "frequency": 3, "document_frequency": 2})

	def test_analytics_update_after_deleting_a_document(self) -> None:
		first = self._ingest("one.txt", "python python")
		self._ingest("two.txt", "python database")
		self.assertTrue(delete_document(first["document_id"], self.storage_directory))

		summary = get_collection_summary(self.storage_directory)
		terms = get_term_analytics(storage_directory=self.storage_directory)

		self.assertEqual(summary["total_documents"], 1)
		self.assertEqual(summary["total_words"], 2)
		self.assertEqual(
			terms,
			[
				{"term": "database", "frequency": 1, "document_frequency": 1},
				{"term": "python", "frequency": 1, "document_frequency": 1},
			],
		)


if __name__ == "__main__":
	unittest.main()
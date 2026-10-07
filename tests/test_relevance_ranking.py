"""Tests for inverted-index keyword ranking."""

import tempfile
import unittest
from pathlib import Path

from backend.app.services.document_ingestion import ingest_document
from backend.app.services.index_construction import rebuild_index
from backend.app.services.relevance_ranking import rank_search_results


class RelevanceRankingTests(unittest.TestCase):
	def setUp(self) -> None:
		rebuild_index([])
		self.temporary_directory = tempfile.TemporaryDirectory()
		self.storage_directory = Path(self.temporary_directory.name)

	def tearDown(self) -> None:
		self.temporary_directory.cleanup()
		rebuild_index([])

	def _ingest(self, filename: str, text: str) -> dict[str, object]:
		return ingest_document(filename, text.encode("utf-8"), self.storage_directory)

	def test_ranks_documents_by_matching_evidence(self) -> None:
		phrase_document = self._ingest("phrase.txt", "python database")
		frequency_document = self._ingest("frequency.txt", "python python python database")

		response = rank_search_results("python database", self.storage_directory)

		self.assertEqual(response["documents_searched"], 2)
		self.assertEqual(response["total_matches"], 6)
		self.assertEqual(response["results"][0]["document_id"], frequency_document["document_id"])
		self.assertEqual(response["results"][1]["document_id"], phrase_document["document_id"])

	def test_higher_term_frequency_produces_a_higher_score(self) -> None:
		low_frequency = self._ingest("low.txt", "python")
		high_frequency = self._ingest("high.txt", "python python python")

		response = rank_search_results("python", self.storage_directory)
		scores = {result["document_id"]: result["relevance_score"] for result in response["results"]}

		self.assertGreater(scores[high_frequency["document_id"]], scores[low_frequency["document_id"]])
		self.assertTrue(all(result["phrase_match_count"] == 0 for result in response["results"]))

	def test_multiple_query_terms_report_each_count(self) -> None:
		document = self._ingest("both.txt", "python near database python")

		response = rank_search_results("python database", self.storage_directory)
		result = response["results"][0]

		self.assertEqual(result["document_id"], document["document_id"])
		self.assertEqual(result["matched_terms"], ["python", "database"])
		self.assertEqual(result["match_counts"], {"python": 2, "database": 1})
		self.assertEqual(result["phrase_match_count"], 0)

	def test_exact_query_phrase_adds_the_documented_bonus(self) -> None:
		self._ingest("phrase.txt", "python database")
		self._ingest("separate.txt", "python and database")

		response = rank_search_results("python database", self.storage_directory)
		results = {result["filename"]: result for result in response["results"]}

		self.assertEqual(results["phrase.txt"]["phrase_match_count"], 1)
		self.assertEqual(results["phrase.txt"]["relevance_score"], 6)
		self.assertEqual(results["separate.txt"]["phrase_match_count"], 0)
		self.assertEqual(results["separate.txt"]["relevance_score"], 4)

	def test_no_matches_returns_empty_ranked_results(self) -> None:
		self._ingest("unrelated.txt", "machine learning")

		response = rank_search_results("python database", self.storage_directory)

		self.assertEqual(response["documents_searched"], 0)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])

	def test_case_insensitive_query_matches_index_terms(self) -> None:
		document = self._ingest("python.txt", "Python DATABASE")

		response = rank_search_results("PYTHON database", self.storage_directory)

		self.assertEqual(response["results"][0]["document_id"], document["document_id"])
		self.assertEqual(response["results"][0]["match_counts"], {"python": 1, "database": 1})

	def test_equal_scores_use_filename_as_deterministic_tie_breaker(self) -> None:
		self._ingest("zeta.txt", "python")
		self._ingest("alpha.txt", "python")

		response = rank_search_results("python", self.storage_directory)

		self.assertEqual([result["filename"] for result in response["results"]], ["alpha.txt", "zeta.txt"])

	def test_empty_query_returns_no_ranked_results(self) -> None:
		self._ingest("python.txt", "python database")

		response = rank_search_results("  !!! ", self.storage_directory)

		self.assertEqual(response["query"], "  !!! ")
		self.assertEqual(response["documents_searched"], 0)
		self.assertEqual(response["total_matches"], 0)
		self.assertEqual(response["results"], [])


if __name__ == "__main__":
	unittest.main()
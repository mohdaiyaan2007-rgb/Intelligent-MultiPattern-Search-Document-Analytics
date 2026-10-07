"""Tests for inverted-index construction and document lifecycle updates."""

import tempfile
import unittest
from pathlib import Path

from backend.app.services.document_ingestion import delete_document, ingest_document, list_documents
from backend.app.services.index_construction import (
    add_document,
    get_index_stats,
    get_postings,
    rebuild_index,
)


class InvertedIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        rebuild_index([])
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage_directory = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_constructs_index_and_tracks_word_positions(self) -> None:
        add_document("doc-1", "Bright search engine")

        self.assertEqual(get_postings("bright"), {"doc-1": [0]})
        self.assertEqual(
            get_index_stats(),
            {
                "total_indexed_documents": 1,
                "total_unique_terms": 3,
                "total_term_occurrences": 3,
            },
        )

    def test_repeated_words_keep_each_position(self) -> None:
        add_document("doc-1", "echo, echo! ECHO.")

        self.assertEqual(get_postings("echo"), {"doc-1": [0, 1, 2]})

    def test_multiple_documents_share_term_postings(self) -> None:
        add_document("doc-1", "red blue")
        add_document("doc-2", "blue green")

        self.assertEqual(get_postings("blue"), {"doc-1": [1], "doc-2": [0]})
        self.assertEqual(get_index_stats()["total_indexed_documents"], 2)

    def test_empty_and_punctuation_only_documents_are_ignored(self) -> None:
        add_document("empty", " \n\t ")
        add_document("punctuation", "... !!! --")

        self.assertEqual(
            get_index_stats(),
            {
                "total_indexed_documents": 0,
                "total_unique_terms": 0,
                "total_term_occurrences": 0,
            },
        )

    def test_ingestion_and_deletion_update_the_index(self) -> None:
        record = ingest_document("colors.txt", b"red blue red", self.storage_directory)

        self.assertEqual(get_postings("red"), {record["document_id"]: [0, 2]})
        self.assertTrue(delete_document(record["document_id"], self.storage_directory))
        self.assertEqual(get_index_stats()["total_indexed_documents"], 0)
        self.assertEqual(get_postings("red"), {})

    def test_rebuilding_from_stored_documents_never_duplicates_postings(self) -> None:
        first = ingest_document("one.txt", b"rain rain", self.storage_directory)
        second = ingest_document("two.md", b"rain sun", self.storage_directory)
        stored_documents = list_documents(self.storage_directory)

        first_stats = rebuild_index(
            stored_documents + stored_documents,
            storage_directory=self.storage_directory,
        )
        second_stats = rebuild_index(storage_directory=self.storage_directory)

        self.assertEqual(first_stats, second_stats)
        self.assertEqual(get_postings("rain"), {
            first["document_id"]: [0, 1],
            second["document_id"]: [0],
        })
        self.assertEqual(second_stats["total_term_occurrences"], 4)


if __name__ == "__main__":
    unittest.main()
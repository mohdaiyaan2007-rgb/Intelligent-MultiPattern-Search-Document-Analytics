"""Basic tests for TXT, Markdown, and CSV document ingestion."""

import json
import tempfile
import unittest
from pathlib import Path

from backend.app.services.document_ingestion import ingest_document, list_documents


class DocumentIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage_directory = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_ingests_txt_and_normalizes_search_text(self) -> None:
        record = ingest_document(
            "notes.txt",
            b"  Hello  WORLD\nfrom TXT.  ",
            self.storage_directory,
        )

        self.assertEqual(record["searchable_text"], "hello world from txt.")
        self.assertEqual(record["original_text"], "  Hello  WORLD\nfrom TXT.  ")
        self.assertEqual(record["file_type"], "txt")
        self.assertEqual(record["word_count"], 4)
        self.assertEqual(len(record["document_id"]), 32)
        self.assertTrue((self.storage_directory / record["stored_filename"]).exists())

    def test_ingests_markdown_and_keeps_original_text(self) -> None:
        source = "# Project Notes\n\nSearchable **markdown** text."
        record = ingest_document("notes.md", source.encode(), self.storage_directory)

        self.assertEqual(record["original_text"], source)
        self.assertEqual(
            record["searchable_text"],
            "# project notes searchable **markdown** text.",
        )
        self.assertEqual(record["file_type"], "md")

    def test_ingests_csv_cells_as_searchable_text(self) -> None:
        source = "Name,Topic\nAda,Pattern Search\n"
        record = ingest_document("topics.csv", source.encode(), self.storage_directory)

        self.assertEqual(record["original_text"], source)
        self.assertEqual(record["searchable_text"], "name topic ada pattern search")
        self.assertEqual(record["file_type"], "csv")

    def test_persists_metadata_and_rejects_unsupported_types(self) -> None:
        ingest_document("notes.txt", b"sample", self.storage_directory)

        metadata = json.loads((self.storage_directory / "metadata.json").read_text())
        self.assertEqual(len(metadata), 1)
        self.assertEqual(len(list_documents(self.storage_directory)), 1)

        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            ingest_document("image.png", b"not text", self.storage_directory)


if __name__ == "__main__":
    unittest.main()
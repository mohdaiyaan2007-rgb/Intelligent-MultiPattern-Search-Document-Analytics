# Intelligent Multi-Pattern Search & Document Analytics Engine

A beginner-friendly BTech CSE project for document ingestion, indexed search, relevance ranking, and analytics. The browser interface brings these existing API features together for project demonstration.

## Project Pipeline

Documents -> Document Ingestion -> Index Construction -> Multi-Pattern Search -> Phrase/Wildcard Search -> Relevance Ranking -> Analytics -> Visualization

## Project Structure

```text
backend/
  app/
    api/
      __init__.py
      routes.py
    services/
      __init__.py
      analytics.py
      document_ingestion.py
      document_loader.py
      index_construction.py
      multi_pattern_search.py
      phrase_wildcard_search.py
      relevance_ranking.py
    __init__.py
    main.py
data/
  documents/
    .gitkeep
    metadata.json              # generated on first upload
    <document-id>.<txt|md|csv> # uploaded source files
frontend/
  css/
    styles.css
  js/
    analytics-data.js
    app.js
  index.html
tests/
  frontend_app.test.cjs
  frontend_visualization.test.cjs
  test_document_ingestion.py
  test_index_construction.py
  test_multi_pattern_search.py
  test_phrase_wildcard_search.py
  test_relevance_ranking.py
requirements.txt
README.md
```

## Technology Stack

- Python 3.10+ and FastAPI for the backend and HTTP API.
- Python standard-library modules for CSV parsing, JSON metadata, tokenization, and the search/index algorithms.
- HTML, CSS, and vanilla JavaScript for the integrated browser UI.
- Node's built-in test runner for frontend behavior tests; no npm packages or chart library are required.
- Uploaded files and metadata are stored under `data/documents/`. SQLite is listed as a possible project option but is not currently used.

## What Each Folder and File Is For

- `backend/`: Python code for the future API and document-search pipeline.
- `backend/app/`: Main FastAPI application package.
- `backend/app/main.py`: Creates the FastAPI application and connects its routes.
- `frontend/`: The browser interface for document management, search, and analytics, served by the API at `/ui/`.
- `backend/app/api/`: HTTP endpoints that the frontend or other clients can call.
- `backend/app/api/routes.py`: Contains health, document-ingestion, index-statistics, multi-pattern, phrase, wildcard, and ranked-search endpoints.
- `backend/app/services/`: Pipeline operations, kept separate so each step can be implemented and explained independently.
- `backend/app/services/document_ingestion.py`: Generates document IDs, stores uploaded files and metadata, and provides document listing and deletion operations.
- `backend/app/services/document_loader.py`: Validates supported file types, decodes UTF-8 text, extracts CSV cell text, and creates normalized searchable text while preserving the source text.
- `backend/app/services/index_construction.py`: Builds and maintains an in-memory inverted index mapping each word to document IDs and word positions.
- `backend/app/services/multi_pattern_search.py`: Builds the Aho-Corasick trie and searches indexed document text for multiple patterns in one scan per document.
- `backend/app/services/phrase_wildcard_search.py`: Verifies exact phrases using consecutive inverted-index positions and expands simple prefix/suffix wildcards using indexed terms.
- `backend/app/services/relevance_ranking.py`: Finds keyword candidates through inverted-index postings, calculates transparent scores, and sorts results deterministically.
- `backend/app/services/analytics.py`: Calculates collection, document, and term statistics from indexed token positions.
- `backend/app/__init__.py`, `backend/app/api/__init__.py`, and `backend/app/services/__init__.py`: Mark these directories as Python packages.
- `data/`: Place for project data kept separate from source code.
- `data/documents/`: Stores uploaded files and `metadata.json`, which keeps each document's metadata and text copies.
- `frontend/index.html`: Application shell with document, search, and analytics views.
- `frontend/css/styles.css`: Responsive styles for the application and Step 8 charts.
- `frontend/js/app.js`: Uses the existing API for uploads, listing/deleting documents, all search modes, and analytics refresh.
- `frontend/js/analytics-data.js`: Maps existing analytics responses into chart rows without recalculating backend metrics.
- `tests/test_document_ingestion.py`: Standard-library unit tests for the three supported file types, metadata persistence, and unsupported file rejection.
- `tests/test_index_construction.py`: Tests word positions, repeated terms, multiple and empty documents, ingestion/deletion updates, and rebuild behavior.
- `tests/test_multi_pattern_search.py`: Tests Aho-Corasick matches, overlaps, repeated patterns, case-insensitivity, empty/missing patterns, snippets, and multiple documents.
- `tests/test_phrase_wildcard_search.py`: Tests exact phrase order and positions, repeated words, case-insensitivity, empty input, prefix/suffix wildcards, and multiple documents.
- `tests/test_relevance_ranking.py`: Tests ranking order, term frequency, multiple terms, phrase bonus, no-match/empty queries, case-insensitivity, and tie-breaking.
- `tests/frontend_app.test.cjs`: Node built-in tests for application markup, uploads, document listing/deletion, search submissions/results, analytics, errors, and empty states.
- `tests/frontend_visualization.test.cjs`: Node built-in tests for analytics chart data mapping and empty collections.
- `requirements.txt`: Python packages needed to run the API, including `python-multipart` for FastAPI file uploads. SQLite support is part of Python's standard library, so it does not need an extra package.
- `README.md`: Project overview, setup steps, pipeline, and structure explanation.

## Run the Application

Use Python 3.10 or newer. On Windows PowerShell, create and activate the project virtual environment, install dependencies, and start the app:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Skip the creation command if `.venv` already exists. If activation is restricted, use the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/ui/` for the integrated browser application. Open `http://127.0.0.1:8000/docs` to inspect or call the API directly. The frontend uses the same-origin endpoints below; it does not duplicate search or analytics calculations.

- `POST /documents`: Upload one supported document using the `file` form field.
- `POST /documents/batch`: Upload multiple documents using repeated `files` form fields. Successful documents and per-file errors are returned separately.
- `GET /documents`: List indexed document metadata.
- `DELETE /documents/{document_id}`: Remove an indexed document and its stored file.
- `GET /index/stats`: Return the indexed document, unique term, and term occurrence counts.
- `GET /analytics/summary`: Return document/token totals, average length, and shortest/longest document lengths.
- `GET /analytics/documents`: Return per-document token count, unique terms, and the five most frequent terms.
- `GET /analytics/terms?limit=10`: Return top collection terms by frequency, with document frequency and alphabetical tie-breaking.
- `GET /ui/`: View the integrated application and analytics charts.
- `POST /search/multi-pattern`: Search multiple patterns with JSON such as `{"patterns": ["python", "database", "machine learning"]}`.
- `POST /search/phrase`: Search an exact consecutive phrase with JSON such as `{"phrase": "machine learning"}`.
- `POST /search/wildcard`: Search terms with a simple leading or trailing `*`, such as `{"pattern": "pyth*"}` or `{"pattern": "*base"}`. The literal portion must be one word; `*` alone matches nothing, and internal or multiple asterisks are rejected.
- `POST /search/ranked`: Rank keyword results with JSON such as `{"query": "python database"}`.
- `GET /health`: Check that the API is responding.

Uploads are limited to 10 MiB each and must be UTF-8 text. Filenames are not used as storage paths; files are stored under generated IDs in `data/documents/`. CSV rows are converted to searchable text while the original CSV text is retained. Search text is lowercased and whitespace-normalized; Markdown markup is retained as text. Metadata counts refer to the normalized searchable text.

Run the Python test suite with:

```bash
python -m unittest discover -s tests
```

Run the complete frontend test suite with Node's built-in runner (no npm package is required):

```bash
node --test tests/frontend_visualization.test.cjs tests/frontend_app.test.cjs
```

The application provides document upload/list/delete, multi-pattern search, exact phrase search, prefix/suffix wildcard search, ranked keyword search, and collection analytics. The flow is: upload supported files, let ingestion store and index them, run searches through the existing API, and review index-backed analytics in the dashboard. Document additions and deletions update the in-memory index immediately; refresh the collection button to reload list, index status, and analytics.

The inverted index tokenizes lowercase searchable text into Unicode word sequences, treating punctuation as a separator. Positions are zero-based word positions, so later phrase search can check whether query words appear consecutively. The index is rebuilt from stored document metadata when the API starts and is updated when documents are uploaded or deleted. Since it is in memory, it is local to the running API process.

The Aho-Corasick matcher inserts patterns into a shared character trie. Failure links continue scanning from the longest suffix that is still a trie prefix, and output links report patterns that finish at that suffix. This finds overlapping patterns too. Search reads normalized text from ingested documents, filters to document IDs present in the inverted index, and returns positions and snippets from that searchable text.

Phrase search tokenizes the query the same way as ingestion and uses each word's postings to find document candidates. It then verifies that the words occur at consecutive positions, including repeated words. Phrase and wildcard positions are zero-based word offsets; snippets are extracted around the corresponding words in searchable text. Wildcard search supports only a non-empty word prefix followed by `*`, or `*` followed by a non-empty word suffix; it matches terms from the current index vocabulary rather than evaluating regular expressions.

Ranked search uses distinct normalized query terms and the inverted index to retrieve only documents containing at least one query term. For each result, the score is `total query-term occurrences + distinct query terms matched + 2 * exact full-query phrase occurrences` (phrase bonus is zero for a one-word query). `total_matches` counts query-term occurrences across returned candidates. This is a small transparent project formula, not a full web-search ranking system; it does not use link analysis, personalized results, or benchmark claims.

Analytics derives token and term counts from the inverted index. Term frequency counts all indexed positions for a term; document frequency counts the number of distinct documents containing that term. Collection averages use indexed documents only, and empty collections report zero for length metrics. Per-document and term ties are ordered deterministically.

The frontend is a lightweight integration layer over the existing API. It does not replace backend search, ranking, ingestion, index, or analytics logic. No performance measurements are included.

## College Demo Flow

A short 5-10 minute presentation can follow this sequence:

1. Start FastAPI and open `http://127.0.0.1:8000/ui/`.
2. Show the existing indexed documents and their token counts.
3. Upload a small TXT file containing `python`, `database`, and the phrase `python database`.
4. Refresh the collection and show document and index statistics updating.
5. Run multi-pattern search for `python, database, machine learning`.
6. Search the exact phrase `python database`.
7. Demonstrate both wildcard forms: `pyth*` and `*base`.
8. Run ranked search for `python database` and show the ordered scores.
9. Open the Analytics view.
10. Explain the document-length, term-frequency, and document-frequency charts.
11. Delete the TXT file uploaded in step 3.
12. Refresh and show that the file, its indexed terms, search matches, and analytics counts are gone.

## Viva Questions and Answers

1. **What is an inverted index?** A mapping from each normalized word to document IDs and the positions of that word in each document.
2. **Why is an inverted index useful?** It lets searches look up postings for query words rather than scan every document's full text for each word.
3. **What is Aho-Corasick?** A multi-pattern string-matching algorithm that puts patterns into a trie and scans a text while following failure and output links.
4. **Why use it instead of searching each pattern separately?** All requested patterns share one scan of each indexed document; the implementation shares trie prefixes and reports overlapping matches.
5. **What are trie nodes?** States for prefixes of the submitted patterns, connected by character edges.
6. **What are failure links?** Links to the longest suffix of the current trie path that is also a trie prefix, used when the next character does not match.
7. **What are output or match links?** Links to suffix states that finish patterns, so shorter patterns ending at the same character are also returned.
8. **How does phrase search work?** It gets index postings for the query words, intersects candidate documents, then checks consecutive positions in order.
9. **How are consecutive phrase words verified?** For a phrase starting at word position `p`, word `i` must have a posting at `p + i`; the positions are zero-based.
10. **How does wildcard search work?** It compares a literal prefix or suffix with terms already in the inverted-index vocabulary.
11. **Which wildcard forms are supported?** A single trailing `*` for a prefix (`pyth*`) or leading `*` for a suffix (`*base`), with a single word literal. Internal/multiple stars are rejected; `*` alone matches nothing.
12. **What is term frequency?** The number of occurrences of a term, counted from the length of its indexed position lists.
13. **What is document frequency?** The number of distinct document IDs whose postings contain that term.
14. **How is relevance ranking calculated?** `score = total occurrences of distinct query terms + distinct query terms matched + 2 * exact full-query phrase matches`. The phrase bonus is zero for a single-word query.
15. **Why use deterministic tie-breaking?** Sorting equal scores by case-insensitive filename and then document ID makes repeated result ordering stable.
16. **What analytics does the project provide?** Indexed document and token totals, unique terms, average/shortest/longest lengths, per-document frequent terms, collection term frequency, and document frequency.
17. **How does the frontend talk to FastAPI?** Vanilla JavaScript uses same-origin `fetch` calls to the existing JSON and multipart endpoints.
18. **Why use FastAPI?** It provides typed request validation, asynchronous upload handling, HTTP routing, and generated OpenAPI/Swagger documentation.
19. **How are documents added and removed from the index?** Ingestion saves a file and metadata, then adds postings; deletion removes the file, metadata, and postings. Startup rebuilds the in-memory index from stored metadata.
20. **What happens when a search finds nothing?** The API returns an empty results list and zero matches; the UI shows a no-results state.

## Known Limitations

- Ingestion is limited to UTF-8 TXT, Markdown, and CSV; PDF/OCR and binary formats are not implemented.
- The inverted index is in memory for one API process and is rebuilt from JSON metadata at startup; there is no shared multi-worker index or SQLite persistence.
- Wildcards support only one leading or trailing `*` on a single word.
- Ranking is the small documented project formula, not a full web-search ranking system.
- The app has no user authentication or historical search-analytics store.
- No benchmark measurements or production-readiness claims are made.
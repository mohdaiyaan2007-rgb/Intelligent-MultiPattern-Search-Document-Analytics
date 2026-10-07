const assert = require("node:assert/strict");
const test = require("node:test");

const { createVisualizationModel } = require("../frontend/js/analytics-data.js");

test("visualization data module initializes with the expected API", () => {
  assert.equal(typeof createVisualizationModel, "function");
  const model = createVisualizationModel({}, [], []);
  assert.deepEqual(model.documentLengths, []);
  assert.deepEqual(model.topTerms, []);
  assert.deepEqual(model.documentFrequencies, []);
});

test("empty analytics responses produce a safe empty-state model", () => {
  const model = createVisualizationModel(
    {
      total_documents: 0,
      total_words: 0,
      unique_terms: 0,
      average_document_length: 0,
    },
    [],
    [],
  );

  assert.equal(model.isEmpty, true);
  assert.deepEqual(model.summary, {
    totalDocuments: 0,
    totalWords: 0,
    uniqueTerms: 0,
    averageDocumentLength: 0,
    shortestDocumentLength: 0,
    longestDocumentLength: 0,
  });
});

test("multiple document analytics become document-length chart rows", () => {
  const model = createVisualizationModel({}, [
    { filename: "brief.txt", word_count: 4 },
    { filename: "long report.md", word_count: 12 },
  ], []);

  assert.deepEqual(model.documentLengths, [
    { label: "brief.txt", value: 4 },
    { label: "long report.md", value: 12 },
  ]);
});

test("top-term visualization uses the existing term-frequency values", () => {
  const model = createVisualizationModel({}, [], [
    { term: "python", frequency: 7, document_frequency: 3 },
    { term: "database", frequency: 4, document_frequency: 2 },
  ]);

  assert.deepEqual(model.topTerms, [
    { label: "python", value: 7 },
    { label: "database", value: 4 },
  ]);
});

test("document-frequency visualization uses endpoint document counts", () => {
  const model = createVisualizationModel({}, [], [
    { term: "python", frequency: 7, document_frequency: 3 },
    { term: "database", frequency: 4, document_frequency: 2 },
  ]);

  assert.deepEqual(model.documentFrequencies, [
    { label: "python", value: 3 },
    { label: "database", value: 2 },
  ]);
});

test("existing analytics response shapes integrate into all dashboard charts", () => {
  const analyticsResponses = {
    summary: {
      total_documents: 2,
      total_words: 9,
      unique_terms: 5,
      average_document_length: 4.5,
    },
    documents: {
      documents: [{ filename: "sample.txt", word_count: 5 }],
    },
    terms: {
      terms: [{ term: "index", frequency: 3, document_frequency: 2 }],
    },
  };

  const model = createVisualizationModel(
    analyticsResponses.summary,
    analyticsResponses.documents.documents,
    analyticsResponses.terms.terms,
  );

  assert.equal(model.summary.totalDocuments, 2);
  assert.equal(model.summary.totalWords, 9);
  assert.deepEqual(model.documentLengths, [{ label: "sample.txt", value: 5 }]);
  assert.deepEqual(model.topTerms, [{ label: "index", value: 3 }]);
  assert.deepEqual(model.documentFrequencies, [{ label: "index", value: 2 }]);
});
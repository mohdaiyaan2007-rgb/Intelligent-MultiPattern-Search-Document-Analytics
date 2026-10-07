(function (root) {
  "use strict";

  function numberOrZero(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  // Adapt the existing analytics responses into chart rows without recalculating metrics.
  function createVisualizationModel(summary, documents, terms) {
    const collection = summary || {};
    const documentRows = Array.isArray(documents) ? documents : [];
    const termRows = Array.isArray(terms) ? terms : [];

    return {
      summary: {
        totalDocuments: numberOrZero(collection.total_documents),
        totalWords: numberOrZero(collection.total_words),
        uniqueTerms: numberOrZero(collection.unique_terms),
        averageDocumentLength: numberOrZero(collection.average_document_length),
        shortestDocumentLength: numberOrZero(collection.shortest_document_length),
        longestDocumentLength: numberOrZero(collection.longest_document_length),
      },
      documentLengths: documentRows.map((document) => ({
        label: String(document.filename || "Unnamed document"),
        value: numberOrZero(document.word_count),
      })),
      topTerms: termRows.map((term) => ({
        label: String(term.term || ""),
        value: numberOrZero(term.frequency),
      })),
      documentFrequencies: termRows.map((term) => ({
        label: String(term.term || ""),
        value: numberOrZero(term.document_frequency),
      })),
      isEmpty: numberOrZero(collection.total_documents) === 0 || documentRows.length === 0,
    };
  }

  const visualizationData = { createVisualizationModel };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = visualizationData;
  }
  if (root) {
    root.AnalyticsVisualizationData = visualizationData;
  }
})(typeof window !== "undefined" ? window : globalThis);
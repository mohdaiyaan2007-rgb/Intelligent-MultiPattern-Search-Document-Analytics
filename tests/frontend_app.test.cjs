const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { createFrontendApp } = require("../frontend/js/app.js");
const { createVisualizationModel } = require("../frontend/js/analytics-data.js");

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.files = [];
    this.value = "";
    this.className = "";
    this._textContent = "";
  }

  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this._textContent = String(value);
    this.children = [];
  }

  get lastChild() {
    return this.children[this.children.length - 1] || null;
  }

  append(...nodes) {
    this.children.push(...nodes);
  }

  replaceChildren(...nodes) {
    this._textContent = "";
    this.children = [];
    this.append(...nodes);
  }

  addEventListener(type, listener) {
    this.listeners[type] ||= [];
    this.listeners[type].push(listener);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  async dispatch(type, event = {}) {
    let result;
    for (const listener of this.listeners[type] || []) {
      result = listener(event);
      if (result && typeof result.then === "function") await result;
    }
    return result;
  }
}

class FakeDocument {
  constructor() {
    this.elements = new Map();
  }

  getElementById(id) {
    if (!this.elements.has(id)) this.elements.set(id, new FakeElement("div"));
    return this.elements.get(id);
  }

  createElement(tagName) {
    return new FakeElement(tagName);
  }
}

class FakeFormData {
  constructor() {
    this.entries = [];
  }

  append(...entry) {
    this.entries.push(entry);
  }
}

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function baseHandlers(documents = []) {
  return {
    "GET /documents": { documents },
    "GET /index/stats": {
      total_indexed_documents: documents.length,
      total_unique_terms: 4,
      total_term_occurrences: 8,
    },
    "GET /analytics/summary": {
      total_documents: documents.length,
      total_words: 8,
      unique_terms: 4,
      average_document_length: 4,
      shortest_document_length: 3,
      longest_document_length: 5,
    },
    "GET /analytics/documents": { documents },
    "GET /analytics/terms?limit=10": {
      limit: 10,
      terms: [{ term: "python", frequency: 3, document_frequency: 2 }],
    },
  };
}

function createHarness(handlers) {
  const document = new FakeDocument();
  const calls = [];
  const fetch = async (url, options = {}) => {
    const method = options.method || "GET";
    calls.push({ url, options });
    const handler = handlers[`${method} ${url}`] || handlers[url];
    if (handler instanceof Error) throw handler;
    if (typeof handler === "function") {
      const result = await handler(url, options);
      if (result && typeof result.json === "function") return result;
      if (result && Object.hasOwn(result, "status")) {
        return jsonResponse(result.body, result.status);
      }
      return jsonResponse(result);
    }
    if (handler === undefined) throw new Error(`No response configured for ${method} ${url}`);
    if (handler && Object.hasOwn(handler, "status")) {
      return jsonResponse(handler.body, handler.status);
    }
    return jsonResponse(handler);
  };
  const app = createFrontendApp({
    document,
    fetch,
    analyticsData: { createVisualizationModel },
    createFormData: () => new FakeFormData(),
  });
  return { app, document, calls };
}

function findElement(root, predicate) {
  if (predicate(root)) return root;
  for (const child of root.children) {
    const found = findElement(child, predicate);
    if (found) return found;
  }
  return null;
}

test("frontend markup includes navigation, document, search, and analytics views", () => {
  const html = fs.readFileSync(path.join(__dirname, "../frontend/index.html"), "utf8");
  for (const id of [
    "documents-view",
    "search-view",
    "analytics-view",
    "upload-form",
    "multi-form",
    "phrase-form",
    "wildcard-form",
    "ranked-form",
    "document-length-chart",
    "term-frequency-chart",
    "document-frequency-chart",
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
});

test("document list renders filenames, IDs, and delete controls", async () => {
  const record = {
    document_id: "doc-1",
    filename: "notes.md",
    file_type: "md",
    word_count: 8,
  };
  const harness = createHarness(baseHandlers([record]));
  await harness.app.init();

  const rows = harness.document.getElementById("document-rows").children;
  assert.equal(rows.length, 1);
  assert.match(rows[0].textContent, /notes\.md/);
  assert.match(rows[0].textContent, /doc-1/);
  assert.ok(findElement(rows[0], (item) => item.className === "delete-button"));
});

test("multi-pattern form posts the exact request and renders match details", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /search/multi-pattern"] = {
    searched_patterns: ["python", "database"],
    documents_searched: 1,
    total_matches: 2,
    results: [{
      document_id: "doc-2",
      filename: "guide.txt",
      matches: [{
        matched_pattern: "python",
        match_count: 2,
        positions: [0, 19],
        snippets: ["python in context", "another python excerpt"],
      }],
    }],
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("multi-pattern-input").value = "python, database\nmachine learning";

  await harness.document.getElementById("multi-form").dispatch("submit", { preventDefault() {} });

  const call = harness.calls.find((item) => item.url === "/search/multi-pattern");
  assert.deepEqual(JSON.parse(call.options.body), {
    patterns: ["python", "database", "machine learning"],
  });
  const output = harness.document.getElementById("multi-results");
  assert.match(output.textContent, /guide\.txt/);
  assert.match(output.textContent, /2 matches/);
  assert.match(output.textContent, /0, 19/);
  assert.match(output.textContent, /python in context/);
});

test("phrase form posts its phrase and displays returned snippets", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /search/phrase"] = {
    phrase: "machine learning",
    documents_searched: 1,
    total_matches: 1,
    results: [{
      document_id: "doc-3",
      filename: "paper.csv",
      matched_phrase: "machine learning",
      match_count: 1,
      positions: [4],
      snippets: ["machine learning in practice"],
    }],
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("phrase-input").value = "machine learning";

  await harness.document.getElementById("phrase-form").dispatch("submit", { preventDefault() {} });

  const call = harness.calls.find((item) => item.url === "/search/phrase");
  assert.deepEqual(JSON.parse(call.options.body), { phrase: "machine learning" });
  assert.match(harness.document.getElementById("phrase-results").textContent, /machine learning in practice/);
});

test("wildcard form renders matched terms and backend validation errors", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /search/wildcard"] = {
    pattern: "pyth*",
    documents_searched: 1,
    total_matches: 1,
    matched_terms: ["python"],
    results: [{
      document_id: "doc-4",
      filename: "code.txt",
      matches: [{ matched_term: "python", match_count: 1, positions: [0], snippets: ["python code"] }],
    }],
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("wildcard-input").value = "pyth*";

  await harness.document.getElementById("wildcard-form").dispatch("submit", { preventDefault() {} });

  assert.match(harness.document.getElementById("wildcard-results").textContent, /python/);
  handlers["POST /search/wildcard"] = { status: 400, body: { detail: "Use one '*' at the beginning or end of a word." } };
  harness.document.getElementById("wildcard-input").value = "py*on";

  await harness.document.getElementById("wildcard-form").dispatch("submit", { preventDefault() {} });

  assert.equal(harness.document.getElementById("wildcard-status").dataset.state, "error");
  assert.match(harness.document.getElementById("wildcard-results").textContent, /beginning or end/);
});

test("ranked form displays the score and matched term counts", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /search/ranked"] = {
    query: "python database",
    documents_searched: 1,
    total_matches: 3,
    results: [{
      document_id: "doc-5",
      filename: "ranked.md",
      relevance_score: 7,
      matched_terms: ["python", "database"],
      match_counts: { python: 2, database: 1 },
      phrase_match_count: 1,
      snippet: "python database example",
    }],
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("ranked-input").value = "python database";

  await harness.document.getElementById("ranked-form").dispatch("submit", { preventDefault() {} });

  assert.match(harness.document.getElementById("ranked-results").textContent, /Score 7/);
  assert.match(harness.document.getElementById("ranked-results").textContent, /python: 2/);
  assert.match(harness.document.getElementById("ranked-results").textContent, /1 phrase matches/);
});

test("analytics loading fills overview and the three visualization charts", async () => {
  const harness = createHarness(baseHandlers([
    { document_id: "doc-6", filename: "report.txt", file_type: "txt", word_count: 5 },
  ]));
  await harness.app.init();

  assert.equal(harness.document.getElementById("metric-documents").textContent, "1");
  assert.equal(harness.document.getElementById("metric-shortest").textContent, "3");
  assert.equal(harness.document.getElementById("metric-longest").textContent, "5");
  assert.equal(harness.document.getElementById("document-length-chart").children.length, 2);
  assert.equal(harness.document.getElementById("term-frequency-chart").children.length, 2);
  assert.equal(harness.document.getElementById("document-frequency-chart").children.length, 2);
  assert.ok(harness.calls.some((call) => call.url === "/analytics/terms?limit=10"));
});

test("upload uses the existing endpoint and refreshes the document list", async () => {
  let documents = [];
  const handlers = baseHandlers([]);
  handlers["GET /documents"] = () => ({ documents });
  handlers["POST /documents"] = (_url, options) => {
    assert.equal(options.body.entries[0][0], "file");
    documents = [{ document_id: "new-doc", filename: "new.txt", file_type: "txt", word_count: 2 }];
    return { document: documents[0] };
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("document-files").files = [{ name: "new.txt" }];

  await harness.document.getElementById("upload-form").dispatch("submit", { preventDefault() {} });

  assert.ok(harness.calls.some((call) => call.url === "/documents" && call.options.method === "POST"));
  assert.match(harness.document.getElementById("document-rows").textContent, /new\.txt/);
});

test("upload failures and network errors are shown to the user", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /documents"] = {
    status: 400,
    body: { detail: "Unsupported file type. Supported types: .csv, .md, .txt." },
  };
  handlers["POST /search/ranked"] = new Error("Connection refused");
  const harness = createHarness(handlers);
  await harness.app.init();
  harness.document.getElementById("document-files").files = [{ name: "image.png" }];

  await harness.document.getElementById("upload-form").dispatch("submit", { preventDefault() {} });
  assert.match(harness.document.getElementById("upload-status").textContent, /Unsupported file type/);

  harness.document.getElementById("ranked-input").value = "python";
  await harness.document.getElementById("ranked-form").dispatch("submit", { preventDefault() {} });
  assert.match(harness.document.getElementById("ranked-results").textContent, /Connection refused/);
  assert.equal(harness.document.getElementById("ranked-status").dataset.state, "error");
});

test("delete action calls the existing endpoint and refreshes collection state", async () => {
  let documents = [{ document_id: "delete-me", filename: "old.txt", file_type: "txt", word_count: 3 }];
  const handlers = baseHandlers([]);
  handlers["GET /documents"] = () => ({ documents });
  handlers["DELETE /documents/delete-me"] = () => {
    documents = [];
    return { status: 204, body: null };
  };
  const harness = createHarness(handlers);
  await harness.app.init();
  const deleteButton = findElement(
    harness.document.getElementById("document-rows"),
    (item) => item.className === "delete-button",
  );

  await deleteButton.dispatch("click");

  assert.ok(harness.calls.some((call) => call.url === "/documents/delete-me" && call.options.method === "DELETE"));
  assert.equal(harness.document.getElementById("document-rows").children.length, 0);
  assert.equal(harness.document.getElementById("documents-empty").hidden, false);
});

test("empty inputs and empty search results show clear states", async () => {
  const handlers = baseHandlers([]);
  handlers["POST /search/multi-pattern"] = {
    searched_patterns: ["missing"],
    documents_searched: 0,
    total_matches: 0,
    results: [],
  };
  const harness = createHarness(handlers);
  await harness.app.init();

  await harness.document.getElementById("multi-form").dispatch("submit", { preventDefault() {} });
  assert.equal(harness.document.getElementById("multi-status").dataset.state, "error");
  harness.document.getElementById("multi-pattern-input").value = "missing";
  await harness.document.getElementById("multi-form").dispatch("submit", { preventDefault() {} });

  assert.match(harness.document.getElementById("multi-results").textContent, /No documents matched/);
  assert.equal(harness.document.getElementById("multi-status").dataset.state, "empty");
});
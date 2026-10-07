(function (root) {
	"use strict";

	const VIEW_NAMES = ["documents", "search", "analytics"];
	const SEARCH_MODES = ["multi", "phrase", "wildcard", "ranked"];

	function createFrontendApp(dependencies) {
		const document = dependencies.document;
		const fetchRequest = dependencies.fetch;
		const analyticsData = dependencies.analyticsData;
		const createFormData = dependencies.createFormData || (() => new root.FormData());

		function element(id) {
			return document.getElementById(id);
		}

		function makeElement(tagName, className, text) {
			const node = document.createElement(tagName);
			if (className) node.className = className;
			if (text !== undefined) node.textContent = String(text);
			return node;
		}

		function setAppStatus(message, state) {
			const status = element("app-status");
			status.hidden = !message;
			status.dataset.state = state || "info";
			status.textContent = message || "";
		}

		function setInlineStatus(id, message, state) {
			const status = element(id);
			status.hidden = !message;
			status.dataset.state = state || "info";
			status.textContent = message || "";
		}

		function setAnalyticsStatus(message, state) {
			element("load-status").dataset.state = state;
			element("load-status-text").textContent = message;
		}

		function formatNumber(value) {
			return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
		}

		function formatUnit(value, unit) {
			return value === 1 && unit.endsWith("s") ? unit.slice(0, -1) : unit;
		}

		async function apiRequest(path, options) {
			const response = await fetchRequest(path, options || {});
			let payload = null;
			if (response.status !== 204) {
				try {
					payload = await response.json();
				} catch (_error) {
					payload = null;
				}
			}

			if (!response.ok) {
				let detail = payload && payload.detail;
				if (Array.isArray(detail)) {
					detail = detail.map((item) => item.msg).filter(Boolean).join("; ");
				}
				throw new Error(detail || `Request failed (${response.status}).`);
			}
			return payload;
		}

		function showEmptyState(container, message, isError) {
			container.replaceChildren();
			container.hidden = false;
			const notice = makeElement("p", isError ? "empty-state empty-state--error" : "empty-state", message);
			container.append(notice);
		}

		function appendSummary(container, values) {
			const summary = makeElement("div", "search-summary");
			for (const [labelText, valueText] of values) {
				const item = makeElement("div", "search-summary-item");
				item.append(makeElement("span", "summary-label", labelText));
				item.append(makeElement("strong", "summary-value", valueText));
				summary.append(item);
			}
			container.append(summary);
		}

		function appendTagList(container, values, className) {
			const list = makeElement("div", className || "tag-list");
			for (const value of values || []) {
				list.append(makeElement("span", "term-tag", value));
			}
			container.append(list);
		}

		function appendDocumentHeading(container, result) {
			const heading = makeElement("div", "result-document-heading");
			heading.append(makeElement("h3", "result-filename", result.filename || "Unnamed document"));
			heading.append(makeElement("code", "result-id", result.document_id || ""));
			container.append(heading);
		}

		function appendMatchDetails(container, positions, snippets) {
			if (Array.isArray(positions) && positions.length) {
				container.append(makeElement("p", "match-positions", `Positions: ${positions.join(", ")}`));
			}
			for (const snippet of snippets || []) {
				container.append(makeElement("blockquote", "match-snippet", snippet));
			}
		}

		function appendMatchBlock(container, title, count, positions, snippets, extra) {
			const block = makeElement("section", "match-block");
			const heading = makeElement("div", "match-heading");
			heading.append(makeElement("h4", "", title));
			heading.append(makeElement("span", "match-count", `${formatNumber(count)} ${count === 1 ? "match" : "matches"}`));
			block.append(heading);
			if (extra) block.append(extra);
			appendMatchDetails(block, positions, snippets);
			container.append(block);
		}

		function appendNoResults(container, message) {
			container.append(makeElement("p", "empty-state", message));
		}

		function renderMultiPatternResults(container, response) {
			container.replaceChildren();
			container.hidden = false;
			appendSummary(container, [
				["Documents searched", response.documents_searched],
				["Total matches", response.total_matches],
			]);
			appendTagList(container, response.searched_patterns, "searched-patterns");
			if (!response.results.length) {
				appendNoResults(container, "No documents matched these patterns.");
				return;
			}

			for (const result of response.results) {
				const card = makeElement("article", "result-card");
				appendDocumentHeading(card, result);
				for (const match of result.matches) {
					appendMatchBlock(
						card,
						match.matched_pattern,
						match.match_count,
						match.positions,
						match.snippets,
					);
				}
				container.append(card);
			}
		}

		function renderPhraseResults(container, response) {
			container.replaceChildren();
			container.hidden = false;
			appendSummary(container, [
				["Documents searched", response.documents_searched],
				["Total matches", response.total_matches],
			]);
			if (!response.results.length) {
				appendNoResults(container, "No exact phrase matches were found.");
				return;
			}

			for (const result of response.results) {
				const card = makeElement("article", "result-card");
				appendDocumentHeading(card, result);
				appendMatchBlock(
					card,
					result.matched_phrase,
					result.match_count,
					result.positions,
					result.snippets,
				);
				container.append(card);
			}
		}

		function renderWildcardResults(container, response) {
			container.replaceChildren();
			container.hidden = false;
			appendSummary(container, [
				["Documents searched", response.documents_searched],
				["Total matches", response.total_matches],
			]);
			const matchedTerms = makeElement("div", "matched-term-summary");
			matchedTerms.append(makeElement("span", "summary-label", "Matched terms"));
			if (response.matched_terms.length) {
				appendTagList(matchedTerms, response.matched_terms, "searched-patterns");
			} else {
				matchedTerms.append(makeElement("span", "muted-copy", "None"));
			}
			container.append(matchedTerms);
			if (!response.results.length) {
				appendNoResults(container, "No indexed terms matched this wildcard.");
				return;
			}

			for (const result of response.results) {
				const card = makeElement("article", "result-card");
				appendDocumentHeading(card, result);
				for (const match of result.matches) {
					appendMatchBlock(
						card,
						match.matched_term,
						match.match_count,
						match.positions,
						match.snippets,
					);
				}
				container.append(card);
			}
		}

		function renderRankedResults(container, response) {
			container.replaceChildren();
			container.hidden = false;
			appendSummary(container, [
				["Documents searched", response.documents_searched],
				["Total matches", response.total_matches],
			]);
			if (!response.results.length) {
				appendNoResults(container, "No documents matched this query.");
				return;
			}

			response.results.forEach((result, index) => {
				const card = makeElement("article", "result-card ranked-result");
				const heading = makeElement("div", "result-document-heading");
				heading.append(makeElement("span", "rank-number", `#${index + 1}`));
				heading.append(makeElement("h3", "result-filename", result.filename || "Unnamed document"));
				heading.append(makeElement("span", "score-badge", `Score ${formatNumber(result.relevance_score)}`));
				card.append(heading);
				const metadata = makeElement("div", "ranked-metadata");
				metadata.append(makeElement("span", "result-id", `ID ${result.document_id}`));
				metadata.append(makeElement("span", "muted-copy", `${result.phrase_match_count} phrase matches`));
				card.append(metadata);
				const counts = makeElement("div", "term-counts");
				for (const [term, count] of Object.entries(result.match_counts || {})) {
					counts.append(makeElement("span", "term-tag", `${term}: ${count}`));
				}
				card.append(counts);
				card.append(makeElement("blockquote", "match-snippet", result.snippet || ""));
				container.append(card);
			});
		}

		function renderBarChart(container, rows, unit, emptyMessage) {
			container.replaceChildren();
			if (!rows.length) {
				container.append(makeElement("p", "empty-state", emptyMessage));
				return;
			}

			const maximum = rows.reduce((largest, row) => Math.max(largest, row.value), 0);
			const rowList = makeElement("div", "bar-rows");
			for (const row of rows) {
				const chartRow = makeElement("div", "bar-row");
				chartRow.setAttribute("role", "listitem");
				const label = makeElement("span", "bar-label", row.label);
				label.title = row.label;
				const track = makeElement("div", "bar-track");
				track.setAttribute("role", "meter");
				track.setAttribute("aria-valuemin", "0");
				track.setAttribute("aria-valuemax", String(maximum));
				track.setAttribute("aria-valuenow", String(row.value));
				track.setAttribute("aria-label", `${row.label}: ${formatNumber(row.value)} ${formatUnit(row.value, unit)}`);
				const bar = makeElement("span", "bar-fill");
				bar.style.width = `${maximum ? (row.value / maximum) * 100 : 0}%`;
				track.append(bar);
				const value = makeElement("span", "bar-value", `${formatNumber(row.value)} ${formatUnit(row.value, unit)}`);
				chartRow.append(label, track, value);
				rowList.append(chartRow);
			}

			const scale = makeElement("div", "chart-scale");
			scale.append(makeElement("span", "", "0"));
			scale.append(makeElement("span", "", `${formatNumber(maximum)} ${formatUnit(maximum, unit)}`));
			container.append(rowList, scale);
		}

		async function loadDocuments() {
			const rows = element("document-rows");
			const emptyState = element("documents-empty");
			element("documents-table-wrap").hidden = false;
			setInlineStatus("documents-status", "Loading documents...", "loading");
			try {
				const response = await apiRequest("/documents");
				const documents = Array.isArray(response.documents) ? response.documents : [];
				rows.replaceChildren();
				emptyState.hidden = documents.length > 0;
				element("documents-table-wrap").hidden = documents.length === 0;
				for (const record of documents) {
					const row = makeElement("tr", "document-row");
					const filename = makeElement("td", "document-name", record.filename);
					row.append(filename);
					row.append(makeElement("td", "", String(record.file_type || "").toUpperCase()));
					row.append(makeElement("td", "numeric-cell", formatNumber(record.word_count)));
					row.append(makeElement("td", "document-id-cell", record.document_id));
					const actions = makeElement("td", "document-actions");
					const deleteButton = makeElement("button", "delete-button", "Delete");
					deleteButton.type = "button";
					deleteButton.setAttribute("aria-label", `Delete ${record.filename}`);
					deleteButton.dataset.documentId = record.document_id;
					deleteButton.addEventListener("click", async () => {
						await deleteDocument(record.document_id, record.filename, deleteButton);
					});
					actions.append(deleteButton);
					row.append(actions);
					rows.append(row);
				}
				setInlineStatus(
					"documents-status",
					documents.length ? `${documents.length} document${documents.length === 1 ? "" : "s"} indexed` : "No indexed documents",
					documents.length ? "success" : "empty",
				);
				return true;
			} catch (error) {
				rows.replaceChildren();
				emptyState.hidden = false;
				emptyState.textContent = "Document list is unavailable. Refresh to try again.";
				setInlineStatus("documents-status", error.message, "error");
				return false;
			}
		}

		async function loadIndexStats() {
			try {
				const stats = await apiRequest("/index/stats");
				element("index-status").textContent = `${formatNumber(stats.total_indexed_documents)} indexed / ${formatNumber(stats.total_unique_terms)} terms`;
				return true;
			} catch (error) {
				element("index-status").textContent = "Index status unavailable";
				return false;
			}
		}

		function renderAnalytics(model) {
			element("metric-documents").textContent = formatNumber(model.summary.totalDocuments);
			element("metric-words").textContent = formatNumber(model.summary.totalWords);
			element("metric-terms").textContent = formatNumber(model.summary.uniqueTerms);
			element("metric-average").textContent = formatNumber(model.summary.averageDocumentLength);
			element("metric-shortest").textContent = formatNumber(model.summary.shortestDocumentLength);
			element("metric-longest").textContent = formatNumber(model.summary.longestDocumentLength);
			renderBarChart(element("document-length-chart"), model.documentLengths, "tokens", "No indexed documents to compare yet.");
			renderBarChart(element("term-frequency-chart"), model.topTerms, "occurrences", "No indexed terms to show yet.");
			renderBarChart(element("document-frequency-chart"), model.documentFrequencies, "documents", "No term distribution to show yet.");
		}

		async function loadAnalytics() {
			setInlineStatus("analytics-status", "Loading analytics...", "loading");
			setAnalyticsStatus("Loading analytics", "loading");
			try {
				// The analytics service remains the source for every value and chart row.
				const [summary, documents, terms] = await Promise.all([
					apiRequest("/analytics/summary"),
					apiRequest("/analytics/documents"),
					apiRequest("/analytics/terms?limit=10"),
				]);
				const model = analyticsData.createVisualizationModel(summary, documents.documents, terms.terms);
				renderAnalytics(model);
				const message = model.isEmpty ? "No indexed documents yet" : `Updated ${new Date().toLocaleTimeString()}`;
				setAnalyticsStatus(message, "ready");
				setInlineStatus("analytics-status", model.isEmpty ? "Analytics are ready when documents are indexed." : "Analytics updated.", model.isEmpty ? "empty" : "success");
				return true;
			} catch (error) {
				setAnalyticsStatus("Analytics unavailable", "error");
				setInlineStatus("analytics-status", error.message, "error");
				return false;
			}
		}

		async function loadCollectionData() {
			return Promise.all([loadDocuments(), loadAnalytics(), loadIndexStats()]);
		}

		async function refreshAll() {
			const button = element("refresh-all-button");
			button.disabled = true;
			setAppStatus("Refreshing documents, index, and analytics...", "loading");
			try {
				const results = await loadCollectionData();
				const success = results.every(Boolean);
				setAppStatus(success ? "Collection refreshed." : "Some collection data could not be refreshed.", success ? "success" : "error");
				return success;
			} finally {
				button.disabled = false;
			}
		}

		async function refreshDocuments() {
			const button = element("refresh-documents-button");
			button.disabled = true;
			const previousText = button.textContent;
			button.textContent = "Loading...";
			try {
				const success = await loadDocuments();
				setAppStatus(success ? "Document list refreshed." : "Could not refresh documents.", success ? "success" : "error");
			} finally {
				button.disabled = false;
				button.textContent = previousText;
			}
		}

		async function refreshAfterChange() {
			await loadCollectionData();
		}

		async function uploadDocuments(event) {
			if (event && event.preventDefault) event.preventDefault();
			const files = Array.from(element("document-files").files || []);
			if (!files.length) {
				setInlineStatus("upload-status", "Choose at least one TXT, Markdown, or CSV file.", "error");
				setAppStatus("No files selected.", "error");
				return false;
			}

			const button = element("upload-button");
			const fileInput = element("document-files");
			const previousText = button.textContent;
			button.disabled = true;
			fileInput.disabled = true;
			button.textContent = "Uploading...";
			setInlineStatus("upload-status", "Uploading and indexing files...", "loading");
			try {
				const formData = createFormData();
				let uploaded;
				let errors = [];
				if (files.length === 1) {
					formData.append("file", files[0], files[0].name);
					const response = await apiRequest("/documents", { method: "POST", body: formData });
					uploaded = response.document ? [response.document] : [];
				} else {
					for (const file of files) formData.append("files", file, file.name);
					const response = await apiRequest("/documents/batch", { method: "POST", body: formData });
					uploaded = response.documents || [];
					errors = response.errors || [];
				}
				fileInput.value = "";
				await refreshAfterChange();
				const message = errors.length
					? `${uploaded.length} uploaded; ${errors.length} file${errors.length === 1 ? "" : "s"} rejected: ${errors[0].error}`
					: `${uploaded.length} document${uploaded.length === 1 ? "" : "s"} uploaded and indexed.`;
				setInlineStatus("upload-status", message, errors.length ? "error" : "success");
				setAppStatus(message, errors.length ? "error" : "success");
				return errors.length === 0;
			} catch (error) {
				setInlineStatus("upload-status", error.message, "error");
				setAppStatus(`Upload failed: ${error.message}`, "error");
				return false;
			} finally {
				button.disabled = false;
				fileInput.disabled = false;
				button.textContent = previousText;
			}
		}

		async function deleteDocument(documentId, filename, button) {
			if (button) button.disabled = true;
			setAppStatus(`Deleting ${filename}...`, "loading");
			try {
				await apiRequest(`/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
				await refreshAfterChange();
				setAppStatus(`${filename} deleted.`, "success");
				return true;
			} catch (error) {
				setAppStatus(`Delete failed: ${error.message}`, "error");
				return false;
			} finally {
				if (button) button.disabled = false;
			}
		}

		function setSearchMode(mode) {
			for (const name of SEARCH_MODES) {
				const active = name === mode;
				element(`mode-tab-${name}`).setAttribute("aria-selected", String(active));
				element(`search-panel-${name}`).hidden = !active;
				element(`${name}-results`).hidden = true;
			}
			element("results-placeholder").hidden = false;
		}

		function setView(view) {
			for (const name of VIEW_NAMES) {
				const active = name === view;
				element(`${name}-view`).hidden = !active;
				const navigationButton = element(`nav-${name}`);
				if (active) navigationButton.setAttribute("aria-current", "page");
				else navigationButton.removeAttribute("aria-current");
			}
		}

		async function runSearch(options) {
			const button = element(options.buttonId);
			const target = element(options.resultsId);
			const previousText = button.textContent;
			button.disabled = true;
			button.textContent = "Searching...";
			element("results-placeholder").hidden = true;
			for (const mode of SEARCH_MODES) element(`${mode}-results`).hidden = mode !== options.mode;
			setInlineStatus(options.statusId, "Searching indexed documents...", "loading");
			setAppStatus("Search in progress...", "loading");
			try {
				const response = await apiRequest(options.path, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(options.body),
				});
				options.render(target, response);
				const hasResults = response.results && response.results.length > 0;
				const message = hasResults ? "Search complete." : "No results found.";
				setInlineStatus(options.statusId, message, hasResults ? "success" : "empty");
				setAppStatus(message, hasResults ? "success" : "empty");
				return response;
			} catch (error) {
				showEmptyState(target, error.message, true);
				setInlineStatus(options.statusId, error.message, "error");
				setAppStatus(error.message, "error");
				return null;
			} finally {
				button.disabled = false;
				button.textContent = previousText;
			}
		}

		function searchMulti(event) {
			if (event && event.preventDefault) event.preventDefault();
			const patterns = element("multi-pattern-input").value
				.split(/[\n,]/)
				.map((pattern) => pattern.trim())
				.filter(Boolean);
			if (!patterns.length) {
				setInlineStatus("multi-status", "Enter one or more patterns.", "error");
				setAppStatus("Enter one or more patterns before searching.", "error");
				return Promise.resolve(null);
			}
			return runSearch({
				mode: "multi",
				buttonId: "multi-search-button",
				statusId: "multi-status",
				resultsId: "multi-results",
				path: "/search/multi-pattern",
				body: { patterns },
				render: renderMultiPatternResults,
			});
		}

		function searchPhrase(event) {
			if (event && event.preventDefault) event.preventDefault();
			const phrase = element("phrase-input").value.trim();
			if (!phrase) {
				setInlineStatus("phrase-status", "Enter a phrase to search.", "error");
				setAppStatus("Enter a phrase before searching.", "error");
				return Promise.resolve(null);
			}
			return runSearch({
				mode: "phrase",
				buttonId: "phrase-search-button",
				statusId: "phrase-status",
				resultsId: "phrase-results",
				path: "/search/phrase",
				body: { phrase },
				render: renderPhraseResults,
			});
		}

		function searchWildcard(event) {
			if (event && event.preventDefault) event.preventDefault();
			const pattern = element("wildcard-input").value.trim();
			if (!pattern) {
				setInlineStatus("wildcard-status", "Enter a wildcard such as pyth* or *base.", "error");
				setAppStatus("Enter a wildcard pattern before searching.", "error");
				return Promise.resolve(null);
			}
			return runSearch({
				mode: "wildcard",
				buttonId: "wildcard-search-button",
				statusId: "wildcard-status",
				resultsId: "wildcard-results",
				path: "/search/wildcard",
				body: { pattern },
				render: renderWildcardResults,
			});
		}

		function searchRanked(event) {
			if (event && event.preventDefault) event.preventDefault();
			const query = element("ranked-input").value.trim();
			if (!query) {
				setInlineStatus("ranked-status", "Enter keywords to rank.", "error");
				setAppStatus("Enter a keyword query before searching.", "error");
				return Promise.resolve(null);
			}
			return runSearch({
				mode: "ranked",
				buttonId: "ranked-search-button",
				statusId: "ranked-status",
				resultsId: "ranked-results",
				path: "/search/ranked",
				body: { query },
				render: renderRankedResults,
			});
		}

		function init() {
			for (const view of VIEW_NAMES) {
				element(`nav-${view}`).addEventListener("click", () => setView(view));
			}
			for (const mode of SEARCH_MODES) {
				element(`mode-tab-${mode}`).addEventListener("click", () => setSearchMode(mode));
			}
			element("refresh-all-button").addEventListener("click", refreshAll);
			element("refresh-documents-button").addEventListener("click", refreshDocuments);
			element("upload-form").addEventListener("submit", uploadDocuments);
			element("multi-form").addEventListener("submit", searchMulti);
			element("phrase-form").addEventListener("submit", searchPhrase);
			element("wildcard-form").addEventListener("submit", searchWildcard);
			element("ranked-form").addEventListener("submit", searchRanked);
			setView("documents");
			setSearchMode("multi");
			return refreshAll();
		}

		return {
			init,
			loadDocuments,
			loadAnalytics,
			refreshAll,
			uploadDocuments,
			deleteDocument,
			searchMulti,
			searchPhrase,
			searchWildcard,
			searchRanked,
			setView,
			setSearchMode,
		};
	}

	const frontend = { createFrontendApp };
	if (typeof module !== "undefined" && module.exports) {
		module.exports = frontend;
	}
	if (root) {
		root.DocumentEngineUI = frontend;
	}
	if (root && root.document && root.fetch && root.AnalyticsVisualizationData) {
		const app = createFrontendApp({
			document: root.document,
			fetch: root.fetch.bind(root),
			analyticsData: root.AnalyticsVisualizationData,
			createFormData: () => new root.FormData(),
		});
		root.documentEngineApp = app;
		app.init();
	}
})(typeof window !== "undefined" ? window : globalThis);
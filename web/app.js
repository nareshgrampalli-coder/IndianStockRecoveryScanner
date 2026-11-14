const strategyFields = [
  ["strategy_3_primary", "S3"],
  ["strategy_1_quality", "S1"],
  ["strategy_4_entry_timing", "S4"],
  ["strategy_2_deep_value", "S2"],
];

const provisionalComponents = [
  {
    field: "business_quality_score",
    label: "Business quality",
    weight: 25,
    rule: "ROCE and ROE score 100 at 20% or above, 75 at 15% or above, 50 at 12% or above, otherwise 0; available scores are averaged.",
    inputs: [
      ["ROCE", "roce", "roce_score", "percent"],
      ["ROE", "roe", "roe_score", "percent"],
    ],
  },
  {
    field: "quarterly_growth_score",
    label: "Quarterly growth",
    weight: 25,
    rule: "Quarterly sales and profit growth score 100 at 15% or above, 75 at 10% or above, 50 at 5% or above, otherwise 0; available scores are averaged.",
    inputs: [
      ["Quarterly sales growth", "quarterly_sales_growth", "quarterly_sales_growth_score", "percent"],
      ["Quarterly profit growth", "quarterly_profit_growth", "quarterly_profit_growth_score", "percent"],
    ],
  },
  {
    field: "valuation_score",
    label: "Value / dividend yield",
    weight: 20,
    rule: "P/E scores 100 through 20, 75 through 25, 50 through 35, otherwise 0. Dividend yield scores 100 at 5% or above, 75 at 3%, 50 at 1%, 25 above 0%, and 50 at 0%; available scores are averaged.",
    inputs: [
      ["P/E", "pe", "pe_score", "number"],
      ["Dividend yield", "dividend_yield", "dividend_yield_score", "percent"],
    ],
  },
  {
    field: "payout_sustainability_score",
    label: "Payout sustainability",
    weight: 15,
    rule: "Payout ratio scores 100 through 60%, 75 through 80%, 50 through 100%, and 0 above 100%.",
    inputs: [["Payout ratio", "payout_ratio", "payout_sustainability_score", "percent"]],
  },
  {
    field: "price_correction_score",
    label: "Price correction",
    weight: 15,
    rule: "Drawdown from the 52-week high scores 100 at 50% or more, 75 at 35%, 50 at 25%, 25 at 15%, otherwise 0.",
    inputs: [["Drawdown from 52-week high", "drawdown_pct", "price_correction_score", "percent"]],
  },
];
let activeScoreTrigger = null;

function displayNumber(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "—";
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
}

function numericValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function displayPercent(value) {
  const formatted = displayNumber(value);
  return formatted === "—" ? formatted : `${formatted}%`;
}

function displayRange(low, high) {
  if (low === null || low === undefined || high === null || high === undefined) return "—";
  return `${displayNumber(low, 2)} – ${displayNumber(high, 2)}`;
}

function safeText(value) {
  return value == null ? "" : String(value);
}

function makeTag(active, label) {
  const tag = document.createElement("span");
  tag.className = `tag ${active ? "tag-active" : "tag-inactive"}`;
  tag.textContent = active ? label : "—";
  return tag;
}

function statusMessage(message, isError = false) {
  const status = document.getElementById("status");
  status.textContent = message;
  status.classList.toggle("error", isError);
  status.hidden = !message;
}

async function getJson(endpoint) {
  const response = await fetch(endpoint, { cache: "no-store" });
  let result = await response.json();
  if (
    response.status === 400 &&
    result.error?.includes("Upload the Screener files") &&
    ["/api/copied-screens", "/api/provisional-ranking"].includes(endpoint)
  ) {
    result = await postUploadedFiles(endpoint);
  } else if (!response.ok) {
    throw new Error(result.error || `Request failed (${response.status})`);
  }
  return result;
}

function uploadedFiles() {
  try {
    return JSON.parse(localStorage.getItem("screenerUploads") || "{}");
  } catch {
    throw new Error("Saved upload data is invalid. Clear it and upload the files again.");
  }
}

async function postUploadedFiles(endpoint) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files: uploadedFiles() }),
    cache: "no-store",
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

function startUploadPage() {
  const storageKey = "screenerUploads";
  const form = document.getElementById("upload-form");
  const saved = uploadedFiles();
  const updateName = (key, name) => {
    const target = document.querySelector(`[data-name-for="${key}"]`);
    if (target) target.textContent = name || "No file selected";
  };
  for (const input of form.querySelectorAll('input[type="file"]')) {
    const key = input.dataset.fileKey;
    updateName(key, saved[key]?.name);
    input.addEventListener("change", async () => {
      const file = input.files[0];
      if (!file) return;
      if (file.size > 900_000) {
        input.value = "";
        statusMessage(`${file.name} is larger than the 900 KB per-file limit.`, true);
        return;
      }
      try {
        saved[key] = { name: file.name, content: await file.text() };
        localStorage.setItem(storageKey, JSON.stringify(saved));
        updateName(key, file.name);
        statusMessage(`${file.name} saved in this browser.`);
      } catch (error) {
        statusMessage(`Could not save ${file.name}: ${error.message}`, true);
      }
    });
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const count = Object.keys(uploadedFiles()).length;
    statusMessage(
      count
        ? `${count} file${count === 1 ? "" : "s"} saved in this browser. You can now view the copied tables or ranking.`
        : "Choose at least one CSV or TSV file first.",
      count === 0
    );
  });
  document.getElementById("clear-uploads").addEventListener("click", () => {
    localStorage.removeItem(storageKey);
    for (const input of form.querySelectorAll('input[type="file"]')) {
      input.value = "";
      updateName(input.dataset.fileKey, "");
    }
    statusMessage("Saved uploads cleared from this browser.");
  });
  if (Object.keys(saved).length) {
    statusMessage(`${Object.keys(saved).length} file(s) are saved in this browser.`);
  }
}

function matchesSearch(stock, query) {
  if (!query) return true;
  return [stock.symbol, stock.name, stock.isin]
    .some((value) => safeText(value).toLowerCase().includes(query));
}

function renderScreenTable(stocks) {
  const body = document.getElementById("stock-rows");
  const filter = document.getElementById("strategy-filter").value;
  const query = document.getElementById("search").value.trim().toLowerCase();
  const filtered = stocks.filter((stock) =>
    (filter === "all" || stock[filter]) && matchesSearch(stock, query)
  );
  body.replaceChildren();
  for (const stock of filtered) {
    const row = document.createElement("tr");
    const values = [
      stock.rank ?? "—",
      `${safeText(stock.name)} (${safeText(stock.symbol)})`,
      stock.isin ?? "—",
      displayNumber(stock.combined_score),
      stock.strategy_membership_count ?? "—",
      displayNumber(stock.market_price, 2),
      displayPercent(stock.drawdown_from_1y_high_pct),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = safeText(value);
      row.append(cell);
    }
    for (const [field, label] of strategyFields) {
      const cell = document.createElement("td");
      cell.append(makeTag(stock[field], label));
      row.append(cell);
    }
    body.append(row);
  }
  document.getElementById("result-count").textContent =
    `${filtered.length} of ${stocks.length} stocks`;
}

function renderMetricCards(counts) {
  const metrics = [
    ["Final ranking", counts.final_ranking],
    ["Multi-screen corroboration", counts.multi_screen],
    ["Strategy 3 · primary", counts.strategy_3_primary],
    ["After Strategy 1 · quality", counts.after_quality_filter],
    ["After Strategy 4 · entry timing", counts.after_entry_timing_filter],
    ["Strategy 2 · deep value", counts.strategy_2_deep_value],
  ];
  const grid = document.getElementById("metrics");
  grid.replaceChildren();
  for (const [label, value] of metrics) {
    const card = document.createElement("article");
    card.className = "metric-card";
    const caption = document.createElement("p");
    caption.textContent = label;
    const count = document.createElement("strong");
    count.textContent = safeText(value);
    card.append(caption, count);
    grid.append(card);
  }
}

function renderFinalTable(stocks) {
  const body = document.getElementById("final-rows");
  const query = document.getElementById("search").value.trim().toLowerCase();
  const filtered = stocks.filter((stock) => matchesSearch(stock, query));
  body.replaceChildren();
  for (const stock of filtered) {
    const row = document.createElement("tr");
    const values = [
      stock.rank ?? "—",
      `${safeText(stock.name)} (${safeText(stock.symbol)})`,
      displayNumber(stock.combined_score),
      stock.strategy_membership_count ?? "—",
      displayNumber(stock.strategy_1_score),
      displayNumber(stock.strategy_2_score),
      displayNumber(stock.strategy_3_score),
      displayNumber(stock.strategy_4_score),
      displayNumber(stock.market_price, 2),
      displayPercent(stock.drawdown_from_1y_high_pct),
      `${displayNumber(stock.score_coverage_pct, 0)}%`,
      displayNumber(stock.risk_governance_score),
      safeText(stock.confidence_rating || "Not rated"),
      displayNumber(stock.fair_value_estimate, 2),
      displayRange(stock.suggested_entry_low, stock.suggested_entry_high),
      displayNumber(stock.exit_target, 2),
      displayNumber(stock.stop_loss_invalidation, 2),
      safeText(stock.price_asof || "—"),
      safeText(stock.publication_date || "—"),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = safeText(value);
      row.append(cell);
    }
    body.append(row);
  }
  if (stocks.length === 0) {
    statusMessage("No stocks currently pass any of the four implemented strategy screens. Review the input exports and data availability.");
  } else if (filtered.length === 0) {
    statusMessage("No final candidates match this search.");
  } else {
    statusMessage("");
  }
}

function provisionalStockKey(stock) {
  const identifier = safeText(stock.isin || stock.symbol).trim();
  const value = identifier || safeText(stock.company).trim();
  return `${identifier ? "id" : "company"}:${value.toLowerCase().replace(/[^a-z0-9]/g, "")}`;
}

function renderProvisionalTable(stocks, changes = new Map()) {
  const body = document.getElementById("provisional-rows");
  const query = document.getElementById("search").value.trim().toLowerCase();
  const filtered = stocks.filter((stock) =>
    [stock.company, stock.source_strategies]
      .some((value) => safeText(value).toLowerCase().includes(query))
  );
  body.replaceChildren();
  for (const stock of filtered) {
    const row = document.createElement("tr");
    const capThreshold = stock.market_cap_over_10000 == null
      ? "Unknown"
      : stock.market_cap_over_10000 ? "Yes" : "No";
    const values = [
      stock.market_price,
      stock.market_cap,
      capThreshold,
      stock.drawdown_pct,
      stock.provisional_component_coverage_pct,
      stock.roce,
      stock.roe,
      stock.quarterly_sales_growth,
      stock.quarterly_profit_growth,
      stock.pe,
      stock.dividend_yield,
      stock.payout_ratio,
      stock.quarterly_net_profit,
      stock.quarterly_sales,
      stock.quarterly_net_margin_pct,
      stock.daily_volume,
      stock.daily_return_pct,
      stock.source_strategies ?? "—",
      stock.unavailable_components || "—",
      stock.conflicting_source_values || "—",
    ];
    const change = changes.get(provisionalStockKey(stock));
    const rankCell = document.createElement("td");
    rankCell.textContent = safeText(stock.rank ?? "—");
    if (change?.rank) {
      rankCell.classList.add("ranking-change");
      rankCell.title = "Rank changed since the previous refresh";
    }
    row.append(rankCell);
    const companyCell = document.createElement("td");
    companyCell.textContent = safeText(stock.company ?? "—");
    row.append(companyCell);
    const scoreCell = document.createElement("td");
    if (change?.score) {
      scoreCell.classList.add("ranking-change");
      scoreCell.title = "Provisional score changed since the previous refresh";
    }
    const scoreLink = document.createElement("button");
    scoreLink.type = "button";
    scoreLink.className = "score-link";
    scoreLink.textContent = displayNumber(stock.provisional_score, 2);
    scoreLink.setAttribute("aria-controls", "score-explanation");
    scoreLink.setAttribute("aria-haspopup", "dialog");
    scoreLink.setAttribute("aria-expanded", "false");
    scoreLink.setAttribute("aria-label", `Explain provisional score for ${safeText(stock.company)}`);
    scoreLink.addEventListener("click", () =>
      showProvisionalScoreExplanation(stock, scoreLink)
    );
    scoreCell.append(scoreLink);
    row.append(scoreCell);
    const scoredValues = [
      displayNumber(stock.business_quality_score),
      displayNumber(stock.quarterly_growth_score),
      displayNumber(stock.valuation_score),
      displayNumber(stock.payout_sustainability_score),
      displayNumber(stock.price_correction_score),
    ];
    for (const value of [...scoredValues, ...values]) {
      const cell = document.createElement("td");
      cell.textContent = safeText(value);
      row.append(cell);
    }
    body.append(row);
  }
  document.getElementById("result-count").textContent =
    `${filtered.length} of ${stocks.length} companies`;
}

function showProvisionalScoreExplanation(stock, trigger) {
  const section = document.getElementById("score-explanation");
  const breakdown = document.getElementById("score-breakdown");
  if (activeScoreTrigger) activeScoreTrigger.setAttribute("aria-expanded", "false");
  activeScoreTrigger = trigger;
  activeScoreTrigger.setAttribute("aria-expanded", "true");
  const coverage = provisionalComponents.reduce(
    (total, component) => numericValue(stock[component.field]) !== null
      ? total + component.weight
      : total,
    0,
  );
  const weightedPoints = provisionalComponents.reduce(
    (total, component) => {
      const score = numericValue(stock[component.field]);
      return score !== null ? total + score * component.weight : total;
    },
    0,
  );
  document.getElementById("score-explanation-title").textContent =
    `${stock.company} · provisional score ${displayNumber(stock.provisional_score, 2)}`;
  document.getElementById("score-explanation-equation").textContent =
    coverage
      ? `Score = ${displayNumber(weightedPoints, 2)} weighted points ÷ ${coverage}% available component weight = ${displayNumber(stock.provisional_score, 2)}. Coverage is ${coverage}% of the provisional model, not completeness of company data.`
      : "No score components are available for this company.";
  breakdown.replaceChildren();

  for (const component of provisionalComponents) {
    const score = numericValue(stock[component.field]);
    const item = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = component.label;
    item.append(heading);
    if (score === null) {
      item.append(document.createTextNode(` — unavailable; ${component.weight}% base weight omitted.`));
    } else {
      const effectiveWeight = component.weight / coverage * 100;
      const contribution = score * component.weight / coverage;
      item.append(document.createTextNode(
        ` — ${displayNumber(score, 2)}/100; base weight ${component.weight}%; ` +
        `normalized weight ${displayNumber(effectiveWeight, 2)}%; ` +
        `contributes ${displayNumber(contribution, 2)} points.`
      ));
    }
    const rule = document.createElement("p");
    rule.className = "score-rule";
    rule.textContent = component.rule;
    item.append(rule);
    const inputs = document.createElement("p");
    inputs.className = "muted";
    inputs.textContent = component.inputs.map(([label, field, scoreField, format]) => {
      const value = stock[field];
      const inputScore = numericValue(stock[scoreField]);
      const formatted = format === "percent"
        ? displayPercent(value)
        : displayNumber(value, 2);
      return `${label}: ${formatted} (${inputScore !== null ? `${displayNumber(inputScore, 2)} score points` : "not scored"})`;
    }).join(" · ");
    item.append(inputs);
    breakdown.append(item);
  }
  if (!section.open) section.showModal();
}

async function startScreens() {
  const result = await getJson("/api/screens");
  const render = () => renderScreenTable(result.stocks);
  document.getElementById("search").addEventListener("input", render);
  document.getElementById("strategy-filter").addEventListener("change", render);
  render();
  statusMessage("");
}

async function startDashboard() {
  const result = await getJson("/api/dashboard");
  renderMetricCards(result.counts);
  document.getElementById("search").addEventListener("input", () =>
    renderFinalTable(result.final_candidates)
  );
  renderFinalTable(result.final_candidates);
}

async function startProvisionalRanking() {
  const scoreDialog = document.getElementById("score-explanation");
  document.getElementById("close-score-explanation").addEventListener("click", () =>
    scoreDialog.close()
  );
  scoreDialog.addEventListener("close", () => {
    if (activeScoreTrigger) {
      activeScoreTrigger.setAttribute("aria-expanded", "false");
      activeScoreTrigger.focus();
      activeScoreTrigger = null;
    }
  });
  scoreDialog.addEventListener("click", (event) => {
    if (event.target === scoreDialog) scoreDialog.close();
  });
  const refreshButton = document.getElementById("refresh-ranking");
  let stocks = [];
  let previousSnapshot = null;
  let changes = new Map();
  let refreshInProgress = false;
  let refreshQueued = false;
  try {
    const savedSnapshot = sessionStorage.getItem("provisionalRankingSnapshot");
    previousSnapshot = savedSnapshot ? JSON.parse(savedSnapshot) : null;
  } catch (error) {
    if (error instanceof SyntaxError) {
      statusMessage("Could not read the previous ranking snapshot; change highlighting starts with this refresh.", true);
    } else if (error instanceof DOMException) {
      statusMessage("Previous ranking snapshots are unavailable in this browser; changes can only be compared while this page remains open.", true);
    } else {
      throw error;
    }
  }
  const refreshRanking = async () => {
    if (refreshInProgress) {
      refreshQueued = true;
      return;
    }
    refreshInProgress = true;
    refreshButton.disabled = true;
    statusMessage("Refreshing ranking from the files saved in this browser…");
    try {
      const result = await getJson("/api/provisional-ranking");
      document.getElementById("provisional-count").textContent =
        `${result.summary.companies} companies · all above ₹10,000 Cr market cap`;
      document.getElementById("provisional-sources").textContent =
        `Inputs: ${(result.sources || []).map((source) =>
          `${source.file} (${source.rows} rows)`
        ).join(" · ")}`;
      stocks = result.stocks;
      const currentSnapshot = Object.fromEntries(stocks.map((stock) => [
        provisionalStockKey(stock),
        {
          rank: stock.rank,
          score: numericValue(stock.provisional_score) === null
            ? null
            : Number(Number(stock.provisional_score).toFixed(2)),
        },
      ]));
      let changedRanks = 0;
      let changedScores = 0;
      let newCompanies = 0;
      changes = new Map();
      if (previousSnapshot) {
        for (const stock of stocks) {
          const key = provisionalStockKey(stock);
          const previous = previousSnapshot[key];
          const current = currentSnapshot[key];
          const rankChanged = previous ? previous.rank !== current.rank : true;
          const scoreChanged = previous
            ? previous.score !== current.score
            : current.score !== null;
          if (rankChanged) changedRanks++;
          if (scoreChanged) changedScores++;
          if (!previous) newCompanies++;
          if (rankChanged || scoreChanged) {
            changes.set(key, { rank: rankChanged, score: scoreChanged });
          }
        }
        const removedCompanies = Object.keys(previousSnapshot).filter(
          (key) => !(key in currentSnapshot)
        ).length;
        statusMessage(
          changedRanks || changedScores || removedCompanies
            ? `Ranking updated: ${changedRanks} rank changes, ${changedScores} score changes, ${newCompanies} new companies, ${removedCompanies} removed. Changed rank and score cells are highlighted.`
            : "Ranking refreshed; no rank or score changes."
        );
      } else {
        statusMessage("Ranking loaded. Future rank and score changes will be highlighted.");
      }
      renderProvisionalTable(stocks, changes);
      previousSnapshot = currentSnapshot;
      try {
        sessionStorage.setItem(
          "provisionalRankingSnapshot",
          JSON.stringify(currentSnapshot)
        );
      } catch (error) {
        if (!(error instanceof DOMException)) throw error;
        statusMessage("Ranking loaded, but this browser could not save a comparison snapshot; changes may not be highlighted after reload.", true);
      }
    } finally {
      refreshInProgress = false;
      refreshButton.disabled = false;
      if (refreshQueued) {
        refreshQueued = false;
        window.setTimeout(() => {
          refreshRanking().catch((error) => statusMessage(error.message, true));
        }, 0);
      }
    }
  };
  document.getElementById("search").addEventListener("input", () =>
    renderProvisionalTable(stocks, changes)
  );
  refreshButton.addEventListener("click", () => {
    refreshRanking().catch((error) => statusMessage(error.message, true));
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      refreshRanking().catch((error) => statusMessage(error.message, true));
    }
  });
  window.addEventListener("storage", (event) => {
    if (event.key === "screenerUploads" || event.key === null) {
      refreshRanking().catch((error) => statusMessage(error.message, true));
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      refreshRanking().catch((error) => statusMessage(error.message, true));
    }
  });
  await refreshRanking();
}

function renderCopiedScreen(screen) {
  const head = document.getElementById("copied-headers");
  const body = document.getElementById("copied-rows");
  const query = document.getElementById("search").value.trim().toLowerCase();
  head.replaceChildren();
  body.replaceChildren();
  for (const column of screen.columns) {
    const cell = document.createElement("th");
    cell.textContent = column;
    head.append(cell);
  }
  const filtered = screen.rows.filter((row) =>
    Object.values(row).some((value) => safeText(value).toLowerCase().includes(query))
  );
  for (const record of filtered) {
    const row = document.createElement("tr");
    for (const column of screen.columns) {
      const cell = document.createElement("td");
      cell.textContent = safeText(record[column] ?? "—");
      row.append(cell);
    }
    body.append(row);
  }
  document.getElementById("screen-source").textContent =
    `${screen.source_file} · ${screen.rows.length} copied rows`;
  document.getElementById("result-count").textContent =
    `${filtered.length} of ${screen.rows.length} rows`;
  if (screen.rows.length === 0) {
    statusMessage("This Screener table is empty; the other strategy screens remain available.");
  } else if (filtered.length === 0) {
    statusMessage("No rows in this screen match the search.");
  } else {
    statusMessage("");
  }
}

async function startCopiedScreens() {
  const result = await getJson("/api/copied-screens");
  const select = document.getElementById("screen-select");
  const search = document.getElementById("search");
  select.replaceChildren();
  for (const [index, screen] of result.screens.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${screen.title} (${screen.rows.length})`;
    select.append(option);
  }
  const render = () => {
    const screen = result.screens[Number(select.value)];
    if (screen) renderCopiedScreen(screen);
  };
  select.addEventListener("change", render);
  search.addEventListener("input", render);
  document.getElementById("copied-summary").textContent =
    `${result.summary.screen_count} strategy screens · ${result.summary.row_count} copied rows`;
  render();
}

async function start() {
  try {
    if (document.body.dataset.view === "upload") startUploadPage();
    else if (document.body.dataset.view === "dashboard") await startDashboard();
    else if (document.body.dataset.view === "provisional") await startProvisionalRanking();
    else if (document.body.dataset.view === "copied-screens") await startCopiedScreens();
    else await startScreens();
  } catch (error) {
    statusMessage(error.message, true);
  }
}

start();

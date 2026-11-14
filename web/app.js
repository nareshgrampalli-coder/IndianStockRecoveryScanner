const strategyFields = [
  ["strategy_3_primary", "S3"],
  ["strategy_1_quality", "S1"],
  ["strategy_4_entry_timing", "S4"],
  ["strategy_2_deep_value", "S2"],
];

function displayNumber(value, digits = 1) {
  if (value === null || value === undefined || value === "") return "—";
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
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
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
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

function renderProvisionalTable(stocks) {
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
      stock.rank ?? "—",
      stock.company ?? "—",
      displayNumber(stock.provisional_score),
      displayNumber(stock.business_quality_score),
      displayNumber(stock.quarterly_growth_score),
      displayNumber(stock.valuation_score),
      displayNumber(stock.payout_sustainability_score),
      displayNumber(stock.price_correction_score),
      displayNumber(stock.market_price, 2),
      displayNumber(stock.market_cap, 0),
      capThreshold,
      displayPercent(stock.drawdown_pct),
      displayPercent(stock.provisional_component_coverage_pct),
      displayPercent(stock.roce),
      displayPercent(stock.roe),
      displayPercent(stock.quarterly_sales_growth),
      displayPercent(stock.quarterly_profit_growth),
      displayNumber(stock.pe, 2),
      displayPercent(stock.dividend_yield),
      displayPercent(stock.payout_ratio),
      displayNumber(stock.quarterly_net_profit, 2),
      displayNumber(stock.quarterly_sales, 2),
      displayPercent(stock.quarterly_net_margin_pct),
      displayNumber(stock.daily_volume, 0),
      displayPercent(stock.daily_return_pct),
      stock.source_strategies ?? "—",
      stock.unavailable_components || "—",
      stock.conflicting_source_values || "—",
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = safeText(value);
      row.append(cell);
    }
    body.append(row);
  }
  document.getElementById("result-count").textContent =
    `${filtered.length} of ${stocks.length} companies`;
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
  const result = await getJson("/api/provisional-ranking");
  document.getElementById("provisional-count").textContent =
    `${result.summary.companies} companies · all above ₹10,000 Cr market cap`;
  document.getElementById("search").addEventListener("input", () =>
    renderProvisionalTable(result.stocks)
  );
  renderProvisionalTable(result.stocks);
  statusMessage("");
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
    if (document.body.dataset.view === "dashboard") await startDashboard();
    else if (document.body.dataset.view === "provisional") await startProvisionalRanking();
    else if (document.body.dataset.view === "copied-screens") await startCopiedScreens();
    else await startScreens();
  } catch (error) {
    statusMessage(error.message, true);
  }
}

start();

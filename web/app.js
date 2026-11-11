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

async function start() {
  try {
    if (document.body.dataset.view === "dashboard") await startDashboard();
    else await startScreens();
  } catch (error) {
    statusMessage(error.message, true);
  }
}

start();

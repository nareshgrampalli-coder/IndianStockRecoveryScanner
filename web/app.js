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
    ["Nifty 500 universe", counts.universe],
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
      `${displayNumber(stock.score_coverage_pct, 0)}%`,
      displayNumber(stock.financial_quality_score),
      displayNumber(stock.earnings_growth_component_score),
      displayNumber(stock.valuation_attractiveness_score),
      displayNumber(stock.technical_recovery_score),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = safeText(value);
      row.append(cell);
    }
    body.append(row);
  }
  if (stocks.length === 0) {
    statusMessage("No stocks currently pass Strategy 3 + Strategy 1 + Strategy 4. Review the funnel counts or refresh the screening inputs.");
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

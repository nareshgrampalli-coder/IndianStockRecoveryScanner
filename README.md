# Nifty 500 Screening Workflow

This tool applies four documented strategy rules to manually exported Screener.in CSV data, enriches candidates with Yahoo Finance prices and technicals, consolidates unique matches, and writes a five-screen workbook plus timestamped SQLite snapshots.

## Data sources and limits

- Fundamentals and valuation metrics come from the supplied Screener.in exports. Export a CSV from each of the four saved screens. Include a `Statement Type` or `Financial Basis` column identifying every row as `Consolidated`, plus Symbol and the available metric columns. Exports without explicit consolidated metadata or containing standalone rows are rejected. Include financial period and publication date columns when available; these dates are retained separately and are required for use in historical fundamental backtests. Missing metrics remain unavailable (not zero-scored) and are listed with a completeness-based data-quality score.
- Nifty 500 constituents are downloaded at run time from Nifty Indices.
- The NSE universe loader cleans whitespace, incomplete rows, invalid-ISIN rows, and exact duplicates on every download. Exclusions are reported as warnings; ambiguous symbol/ISIN mappings fail explicitly rather than being guessed.
- RSI, MACD, moving averages, volume and 20-day support proxy are calculated from corporate-action-adjusted Yahoo Finance prices and volume, using NSE `.NS` symbols. Raw and adjusted OHLC are both persisted.
- The constituent list and market data require an internet connection. Yahoo Finance coverage or rate limits can leave individual technical metrics unavailable.
- Screener fundamental values and Yahoo technicals may have different as-of dates; see each workbook row's `price_asof` and the scoring/sources sheet.

## Generate `screening_results.xlsx`

Run the following from the repository root in PowerShell. Activate the existing virtual environment first; keep using this terminal for the commands in this guide.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Prepare four Screener.in CSV exports, one for each strategy. Each export must include a `Statement Type` or `Financial Basis` column whose rows are all `Consolidated`; include a `Symbol` (or company name) column and whatever financial metrics are available. For example, save them as `data\inputs\strategy1.csv` through `data\inputs\strategy4.csv`.

Generate the workbook:

```powershell
python app.py `
  --strategy-1 data\inputs\strategy1.csv `
  --strategy-2 data\inputs\strategy2.csv `
  --strategy-3 data\inputs\strategy3.csv `
  --strategy-4 data\inputs\strategy4.csv `
  --output screening_results.xlsx
```

The script downloads the Nifty 500 constituents and available Yahoo Finance price history, then writes the workbook to the path given by `--output` (default: `screening_results.xlsx`). The workbook includes `Quality_Correction`, `Deep_Value`, `Recovery_30_50`, `Technical_Reversal`, and `Final_Ranking` sheets, plus compatibility/research sheets. It also writes one matching CSV per strategy and `Final_Ranking.csv` to `strategy_results\` by default; change this folder with `--strategy-results-dir`. Results are stored in the shared SQLite database in `config/settings.yaml`; each run creates a historical ranking snapshot with strategy memberships and scores.

The final ranking uses fixed weights: fundamental quality 20, earnings growth 20, valuation attractiveness 15, technical strength 20, recovery potential 15, and risk/governance 10. Membership in multiple strategies is displayed as corroboration but does not add points. Each screen's individual strategy score is also shown. Fair value, entry range, exit target and stop/invalidation remain blank until a calculation methodology is defined; score coverage and source dates are provided instead.

Strategies 1–3 use Yahoo's adjusted one-year high and current price for their correction criteria. Strategy 4 uses Yahoo-derived RSI, MACD, 20-day EMA and volume data. The first run requires internet access; unavailable prices are recorded per stock. To see all options, run `python app.py --help`.

The legacy command `python screening_workflow.py` accepts the same arguments.

### Run one strategy separately

To evaluate and export just one strategy, use `screen_strategy.py` with that strategy's consolidated Screener CSV. The command writes only matching companies to the requested CSV. It still needs internet access to map companies against the current Nifty 500 list; Strategies 2–4 also fetch Yahoo Finance history for their price/technical conditions.

Run the saved query on Screener.in and export its results to CSV first. Screener.in does not provide an official public API for running these custom queries, so this workflow uses the supported UI export and performs a local rule check; it does not log in to or scrape the site. Include the relevant financial columns in each export. Strategies 3 and 4 also require quarterly growth columns (`Quarterly Sales Growth` and/or `Quarterly Profit Growth`).

For example, run Strategy 3 by itself:

```powershell
python screen_strategy.py `
  --strategy strategy_3 `
  --input data\inputs\strategy3.csv `
  --output strategy_results\strategy_3_results.csv
```

Use `strategy_1`, `strategy_2`, `strategy_3`, or `strategy_4` for `--strategy`. Strategies 1–3 use the financial fields from the input plus market price and one-year high from Yahoo; Strategy 4 also checks the fundamental prefilter and uses RSI, MACD, 20-day EMA, and volume data. The output folder is created automatically. For all four CSVs in one run, use the `python app.py` command above.

### Repeatable post-close run

After exporting fresh Screener CSVs to the four `data\inputs\strategy*.csv` paths, run:

```powershell
.\run_daily_screening.ps1
```

The script checks that each input exists, is non-empty, and was modified today, then runs the full five-screen workflow. For unattended weekday runs, configure Windows Task Scheduler to execute this script after market close; Screener CSV exports still need to be refreshed first. Exchange holidays are not automatically detected. Each successful run retains a dated ranking snapshot in the configured SQLite database while refreshing the current workbook and CSVs.

Each Screener CSV must explicitly identify every row as `Consolidated` using a `Statement Type` or `Financial Basis` column. Standalone or unspecified statements are rejected. Include `Financial Period` and `Publication Date` as separate columns for point-in-time backtests; rows without parseable dates are excluded from those backtests. Other metric columns may be absent, but missing values are flagged and remain unscored.

Runtime settings, including history periods, worker count, security mapping path, and SQLite path, are in `config/settings.yaml`.

## Full-universe ingestion

To normalize the full Nifty 500 universe, four consolidated fundamental exports, and daily history:

```powershell
python ingest_data.py `
  --strategy-1 data\inputs\strategy1.csv `
  --strategy-2 data\inputs\strategy2.csv `
  --strategy-3 data\inputs\strategy3.csv `
  --strategy-4 data\inputs\strategy4.csv `
  --output-dir normalized_data `
  --bhavcopy-csv data\inputs\nse_bhavcopy.csv
```

The Bhavcopy argument is optional; include it only after saving an actual NSE Bhavcopy CSV as `data\inputs\nse_bhavcopy.csv`. The file must contain ISIN, trade date, and close price columns. The job writes:

- `normalized_data/normalized_stocks.csv`: one row per Nifty 500 constituent with canonical ISIN, all four strategy memberships, financial fields, provenance, quality, and price-validation status.
- `normalized_data/normalized_daily_prices.csv`: raw and adjusted daily OHLCV history.
- `normalized_data/ingestion_errors.csv`: per-symbol download or normalization errors.

It also persists security mappings, price bars, and consolidated financial observations in the SQLite database configured in `config/settings.yaml` (default: `data/screening.sqlite3`). Yahoo Finance is the currently configured history adapter; see [the architecture guide](docs/architecture.md) for DhanHQ prerequisites and data-source limitations.

## Local web pages

After generating the workbook, start the local dashboard:

```powershell
python dashboard.py --workbook screening_results.xlsx
```

Open `http://127.0.0.1:8000/` for the searchable strategy results, or `http://127.0.0.1:8000/dashboard` for the consolidated final ranking. The dashboard shows all unique stocks passing at least one local strategy rule, strategy membership count, individual screen scores, price/drawdown and data coverage. Strategy overlap does not add bonus points. Verify current data before considering a trade. Stop the local server with `Ctrl+C`.

## Project modules

- `data_sources/` contains NSE Indices and Yahoo Finance providers, the Screener CSV importer, and explicit Dhan, Upstox, and BSE integration boundaries. Dhan/Upstox credentials and BSE disclosure retrieval are not configured.
- `data_processing/`, `indicators/`, `strategies/`, and `scoring/` hold reusable cleaning, indicator, screen-condition, scoring, and ranking functions.
- `backtesting/` provides next-bar, long-only return calculations. `database/` provides a SQLite screening-result repository.
- `dashboard.py` serves a local stock-list page and a separate final-results dashboard from the latest ranked workbook.
- `config/` contains runtime settings and a stock-universe CSV template.
- ISIN is the canonical identifier. `config/stock_universe.csv` maintains ISIN, company name, NSE symbol and BSE symbol mappings; NSE constituent downloads must include ISIN.
- Screening runs persist security mappings, raw/adjusted price bars, and consolidated financial observations with provider, retrieval time and data-quality metadata in the configured SQLite database.
- Fundamental backtests must use `backtest_with_fundamentals`; it rebuilds each signal from prices and consolidated financial observations published before and reported by that session date. Same-day publications and records without parseable period/publication dates are excluded to avoid daily-bar lookahead.

## Tests

Run the unit tests with:

```powershell
python -m unittest discover -s tests -v
```

## Documentation

- [Architecture and data sources](docs/architecture.md)
- [Screening workflow](docs/screening-workflow.md)
- [Strategy 1: Quality correction](docs/strategies/quality-correction.md)
- [Strategy 2: Deep value](docs/strategies/deep-value.md)
- [Strategy 3: Recovery 30–50%](docs/strategies/recovery-30-50.md)
- [Strategy 4: Technical reversal](docs/strategies/technical-reversal.md)

## Scoring outline

The final ranking uses fixed 100-point weights: financial quality 20, earnings growth 20, valuation attractiveness 15, technical strength 20, recovery potential 15, and risk/governance 10. Individual screen profiles still produce per-strategy scores, but do not change the final ranking. Missing components are proportionally renormalized; `score_coverage_pct` reports original-weight coverage. Strategy overlap is an indicator only, not a score bonus. Recovery potential is gated by business-quality and growth evidence, so a large drawdown alone does not improve the score. See [the architecture guide](docs/architecture.md) for definitions. Technical indicators support research and do not replace company analysis.

The tool does not automatically trade, make investment recommendations, or guarantee that a candidate is suitable. Check official filings and data freshness before relying on any result.

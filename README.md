# Nifty 500 Screening Workflow

This tool combines four Screener.in CSV exports into a deduplicated Nifty 500 watchlist, enriches candidates with recent Yahoo Finance technicals, scores the available fundamental and technical metrics, and writes an Excel workbook.

## Data sources and limits

- Fundamentals and valuation metrics come from the supplied Screener.in exports. Export a CSV from each of the four saved screens. Include a `Statement Type` or `Financial Basis` column identifying every row as `Consolidated`, plus Symbol and the available metric columns. Exports without explicit consolidated metadata or containing standalone rows are rejected. Include financial period and publication date columns when available; these dates are retained separately and are required for use in historical fundamental backtests. Missing metrics remain unavailable (not zero-scored) and are listed with a completeness-based data-quality score.
- Nifty 500 constituents are downloaded at run time from Nifty Indices.
- RSI, MACD, moving averages, volume and 20-day support proxy are calculated from corporate-action-adjusted Yahoo Finance prices and volume, using NSE `.NS` symbols. Raw and adjusted OHLC are both persisted.
- The constituent list and market data require an internet connection. Yahoo Finance coverage or rate limits can leave individual technical metrics unavailable.
- Screener fundamental values and Yahoo technicals may have different as-of dates; see each workbook row's `price_asof` and the scoring/sources sheet.

## Setup and run

Use Python 3.10 or newer:

```powershell
python -m pip install -r requirements.txt
python app.py `
  --strategy-1 path\to\strategy1.csv `
  --strategy-2 path\to\strategy2.csv `
  --strategy-3 path\to\strategy3.csv `
  --strategy-4 path\to\strategy4.csv `
  --output screening_results.xlsx
```

The same command-line interface remains available through `screening_workflow.py`. Settings such as the universe URL, history period, and worker count are in `config/settings.yaml`.

## Full-universe ingestion

To normalize the full Nifty 500 universe, four consolidated fundamental exports, and daily history:

```powershell
python ingest_data.py `
  --strategy-1 path\to\strategy1.csv `
  --strategy-2 path\to\strategy2.csv `
  --strategy-3 path\to\strategy3.csv `
  --strategy-4 path\to\strategy4.csv `
  --output-dir normalized_data `
  --bhavcopy-csv path\to\nse_bhavcopy.csv
```

The Bhavcopy argument is optional. The job writes normalized stock and daily-price CSVs plus an ingestion-error report, and persists the data in SQLite. Yahoo Finance is the currently configured history adapter; the architecture document records the remaining DhanHQ credentials, instrument mapping, and corporate-action verification required for production use.

The workbook contains `Ranked Watchlist`, `Top 15 Research`, `Combined Screen Imports`, `Nifty 500 Universe`, and `Scoring & Sources` sheets. Strategy membership and flags are retained for each stock: Strategy 3 is the primary screen, Strategy 1 the quality filter, Strategy 4 the entry-timing filter, and Strategy 2 the deep-value list. Combined score determines ranking, with these strategy flags used as tie-breakers. The first 15 ranked stocks are a research shortlist, not a buy recommendation.

## Project modules

- `data_sources/` contains NSE Indices and Yahoo Finance providers, the Screener CSV importer, and explicit Dhan, Upstox, and BSE integration boundaries. Dhan/Upstox credentials and BSE disclosure retrieval are not configured.
- `data_processing/`, `indicators/`, `strategies/`, and `scoring/` hold reusable cleaning, indicator, screen-condition, scoring, and ranking functions.
- `backtesting/` provides next-bar, long-only return calculations. `database/` provides a SQLite screening-result repository.
- `config/` contains runtime settings and a stock-universe CSV template.
- ISIN is the canonical identifier. `config/stock_universe.csv` maintains ISIN, company name, NSE symbol and BSE symbol mappings; NSE constituent downloads must include ISIN.
- Screening runs persist security mappings, raw/adjusted price bars, and consolidated financial observations with provider, retrieval time and data-quality metadata in the configured SQLite database.
- Fundamental backtests must use `backtest_with_fundamentals`; it rebuilds each signal from prices and consolidated financial observations published before and reported by that session date. Same-day publications and records without parseable period/publication dates are excluded to avoid daily-bar lookahead.

## Scoring outline

Each of the four strategies uses a distinct 100-point component-weight profile. Deep value emphasizes valuation; technical reversal emphasizes its momentum and volume signals. Candidates appearing in multiple strategies receive each applicable strategy score, and the final combined score is their average. Missing components are proportionally renormalized within each profile; `score_coverage_pct` reports average original-weight coverage. Price-correction points are scaled by financial-quality and earnings-growth evidence, so a large drawdown alone does not improve the score. Exact profiles and component definitions are in the architecture document and workbook. Technical indicators are confirmation/monitoring signals; they do not replace company research.

The tool does not automatically trade, make investment recommendations, or guarantee that a candidate is suitable. Check official filings and data freshness before relying on any result.

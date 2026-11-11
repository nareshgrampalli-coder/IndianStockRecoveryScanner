# Nifty 500 Screening Workflow

This tool combines four Screener.in CSV exports into a deduplicated Nifty 500 watchlist, enriches candidates with recent Yahoo Finance technicals, scores the available fundamental and technical metrics, and writes an Excel workbook.

## Data sources and limits

- Fundamentals and valuation metrics come from the supplied Screener.in exports. Export a CSV from each of the four saved screens. Include Symbol and the available metric columns (ROCE, ROE, sales growth, profit/earnings growth, debt/equity, operating cash flow, and P/E). Missing columns are reported as unavailable in scoring rather than fabricated.
- Nifty 500 constituents are downloaded at run time from Nifty Indices.
- RSI, MACD, moving averages, volume and 20-day support proxy are calculated from Yahoo Finance daily adjusted prices and volume, using NSE `.NS` symbols.
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

The workbook contains `Ranked Watchlist`, `Top 15 Research`, `Combined Screen Imports`, `Nifty 500 Universe`, and `Scoring & Sources` sheets. Strategy membership and flags are retained for each stock: Strategy 3 is the primary screen, Strategy 1 the quality filter, Strategy 4 the entry-timing filter, and Strategy 2 the deep-value list. Combined score determines ranking, with these strategy flags used as tie-breakers. The first 15 ranked stocks are a research shortlist, not a buy recommendation.

## Project modules

- `data_sources/` contains NSE Indices and Yahoo Finance providers, the Screener CSV importer, and explicit Dhan, Upstox, and BSE integration boundaries. Dhan/Upstox credentials and BSE disclosure retrieval are not configured.
- `data_processing/`, `indicators/`, `strategies/`, and `scoring/` hold reusable cleaning, indicator, screen-condition, scoring, and ranking functions.
- `backtesting/` provides next-bar, long-only return calculations. `database/` provides a SQLite screening-result repository.
- `config/` contains runtime settings and a stock-universe CSV template.

## Scoring outline

The final score uses a 100-point weighted model: financial quality 25, earnings growth 20, valuation attractiveness 15, technical recovery 20, price correction opportunity 10, and risk/governance 10. Each component is scored 0-100 and contributes according to its weight. When a component is unavailable, the available weights are proportionally renormalized; `score_coverage_pct` shows the total original weight represented by available data. The workbook documents component definitions and thresholds. Technical indicators are confirmation/monitoring signals; they do not replace company research.

The tool does not automatically trade, make investment recommendations, or guarantee that a candidate is suitable. Check official filings and data freshness before relying on any result.

# Stock Screening Platform: Data Sources and Architecture

## Data sources and responsibilities

| Area | Sources | Data / responsibility |
|---|---|---|
| Official exchange data | NSE / BSE | Prices, trading volumes, corporate announcements, and index constituents |
| Market APIs | Upstox / Dhan / FYERS | Historical and live market data |
| Financial data | Screener.in / company filings | Revenue, profit after tax (PAT), ROCE, debt, and cash flow |
| Reference data | NSE / BSE | Company information and corporate actions |
| Technical engine | Python / TA-Lib | RSI, MACD, EMA, SMA, and ADX calculations |

Use company filings and exchange-published information as authoritative sources where available. Treat third-party APIs as delivery mechanisms, record data timestamps and provenance, and account for provider terms, coverage, and rate limits.

## Final source recommendation

| Component | Recommended source |
|---|---|
| Historical prices | DhanHQ |
| Price validation | NSE Bhavcopy |
| Company universe | NSE Indices |
| Financial statements | Screener CSV initially |
| Official financial validation | NSE / BSE |
| Technical indicators | Python |
| Database | PostgreSQL / Supabase |
| Dashboard | React / Vercel |
| Development | VS Code + GitHub Copilot |

Start with daily end-of-day data for all 500 companies rather than live streaming. For a 6–12 month investment horizon, reliable daily prices and quarterly financials are more useful than expensive real-time feeds. Keep provider interfaces independent so sources can be replaced without changing strategy logic.

The current SQLite ingestion pipeline uses Yahoo Finance as its executable historical-price adapter because it supplies adjusted close for corporate-action adjustment. DhanHQ remains the recommended production source, but needs account credentials, an ISIN-to-Dhan instrument mapping, and a verified corporate-action adjustment policy before it can safely replace the current adapter. NSE Bhavcopy validation is supported through a same-session CSV input.

## Normalized ingestion

Run `python ingest_data.py` with the four consolidated Screener exports to download the Nifty 500 universe and daily history for every constituent. It writes `normalized_stocks.csv`, `normalized_daily_prices.csv`, and `ingestion_errors.csv`, and persists ISIN mappings, price bars, and consolidated financial observations in SQLite. An optional `--bhavcopy-csv` argument compares same-session raw closes with NSE Bhavcopy; differences above 0.5% are flagged for review.

## 2. Data source comparison

| Source | Price history | Fundamentals | Technical data | Recommendation |
|---|---|---|---|---|
| NSE India | Excellent EOD | Corporate filings | Some reports | Primary official source |
| BSE India | Excellent EOD | Corporate filings | Some reports | Secondary validation |
| DhanHQ | Excellent | Limited | Calculate yourself | Strong API option |
| Upstox | Excellent | Limited | Calculate yourself | Strong API option |
| FYERS | Excellent | Limited | Calculate yourself | Strong API option |
| Screener.in | Limited | Excellent | Limited | Fundamental research |
| Yahoo Finance | Good | Inconsistent | Calculate yourself | Development/testing |

## 3. Data sources mapped to your four strategies

| Data requirement | Recommended source |
|---|---|
| Nifty 500 membership | NSE Indices |
| Current price | Dhan / Upstox |
| 5-year daily OHLCV | Dhan / Upstox |
| 52-week high/low | NSE + historical prices |
| ROCE / ROE | Screener CSV / filings |
| Quarterly sales growth | NSE / BSE filings |
| Quarterly PAT growth | NSE / BSE filings |
| Debt/equity | Financial statements |
| Operating cash flow | Annual reports / financial statements |
| PE ratio | NSE + calculated PE |
| Promoter holding | NSE / BSE filings |
| Promoter pledging | NSE / BSE filings |
| RSI / MACD / ADX | Python calculations |
| Moving averages | Python calculations |
| Delivery percentage | NSE reports |
| Bulk and block deals | NSE reports |

## 4. Python libraries to use

You do not need an external technical-indicator API. Calculate indicators yourself from historical OHLCV data.

| Library | Purpose |
|---|---|
| `pandas` | Financial data processing |
| `numpy` | Calculations and scoring |
| `yfinance` | Secondary price validation |
| `ta` | RSI, MACD, ADX, Bollinger Bands |
| `TA-Lib` | Technical indicators |
| `requests` | API integration |
| `sqlalchemy` | Database integration |
| `pydantic` | Data validation |
| `backtesting.py` | Strategy backtesting |
| `plotly` | Interactive charts |

## Screening workflow

```text
Four strategies
      ↓
Fundamental scoring
      ↓
Technical scoring
      ↓
Ranked watchlist
```

The Python stock-screening and scoring engine combines results from the four strategies, evaluates fundamental and technical criteria, and produces a ranked watchlist for further research.

## Recommended scoring model

Each strategy uses a 100-point component-weight profile:

| Component | Quality correction | Deep value | Recovery 30–50% | Technical reversal |
|---|---:|---:|---:|---:|
| Financial quality | 25 | 20 | 25 | 15 |
| Earnings growth | 20 | 15 | 25 | 15 |
| Valuation attractiveness | 15 | 25 | 15 | 10 |
| Technical recovery | 20 | 15 | 15 | 35 |
| Price correction opportunity | 10 | 10 | 10 | 15 |
| Risk and governance | 10 | 15 | 10 | 10 |
| **Total** | **100** | **100** | **100** | **100** |

Each component is scored from 0 to 100, then multiplied by its strategy weight. Missing components are excluded and the remaining weights are proportionally renormalized to a 100-point score; `score_coverage_pct` reports average original-weight coverage. Financial quality combines ROCE, ROE, and operating cash flow; earnings growth combines sales and profit growth; valuation uses P/E; risk/governance combines debt/equity with available promoter holding and pledging data.

Technical reversal uses a strategy-specific technical score: momentum is 50% of the component (RSI 40%, MACD 35%, moving averages 25%), volume is 30%, and support is 20%. Price-correction points use drawdown bands from the highest Yahoo adjusted close in the available one-year history, then are multiplied by the mean financial-quality and earnings-growth scores. A large drawdown without either business-recovery signal has no correction score. If a stock appears in multiple screens, its final score is the average of its applicable strategy-profile scores.

## Application architecture

```text
NSE / BSE ─┐
Market APIs ├─→ Python screening and scoring engine ─→ PostgreSQL / Supabase
Filings ────┘                                              ↓
                                                   React dashboard
                                             snapshots, scores, charts,
                                                       and alerts
```

- **Python engine:** imports screening and financial data, calculates indicators and scores, and creates ranked snapshots.
- **PostgreSQL / Supabase:** persists historical snapshots and scores for comparison over time.
- **Local dashboard:** `dashboard.py` serves the searchable four-strategy stock list and a separate final-results funnel from the latest ranked workbook. A hosted React/Vercel dashboard remains a future deployment option.

## Data handling considerations

- Use ISIN as the canonical security identifier and maintain NSE/BSE symbol mappings in the security master.
- Preserve raw and adjusted OHLC; calculate indicators and drawdowns only from corporate-action-adjusted values.
- Use consolidated financial statements consistently. Retain the reporting period separately from the publication date and retrieval timestamp.
- Point-in-time fundamental backtests must only expose consolidated observations whose reporting period is no later than the session and whose publication date is before it (same-day publication timing is unknown).
- Record provider, retrieval time, and completeness-based data quality for price and financial data. Keep missing financial values as unavailable and report them rather than scoring them as zero.
- Persist source and as-of timestamps with imported prices and fundamentals; values from different providers may refer to different dates.
- Track corporate actions and index membership changes when comparing historical snapshots.
- Preserve the provider/source associated with each field so results can be checked against exchange data or filings.
- Keep screening scores as research aids, not investment recommendations.

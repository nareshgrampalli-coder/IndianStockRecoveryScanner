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
- **React dashboard:** displays scores and charts and provides alerts based on configured conditions.

## Data handling considerations

- Persist source and as-of timestamps with imported prices and fundamentals; values from different providers may refer to different dates.
- Track corporate actions and index membership changes when comparing historical snapshots.
- Preserve the provider/source associated with each field so results can be checked against exchange data or filings.
- Keep screening scores as research aids, not investment recommendations.

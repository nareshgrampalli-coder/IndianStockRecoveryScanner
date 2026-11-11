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

The final rank uses a 100-point weighted model across the four strategies:

| Component | Weight |
|---|---:|
| Financial quality | 25 |
| Earnings growth | 20 |
| Valuation attractiveness | 15 |
| Technical recovery | 20 |
| Price correction opportunity | 10 |
| Risk and governance | 10 |
| **Total** | **100** |

Each component is scored from 0 to 100, then multiplied by its weight. Missing components are excluded and the remaining weights are proportionally renormalized to a 100-point score; `score_coverage_pct` reports the sum of available original weights. Financial quality combines ROCE, ROE, and operating cash flow; earnings growth combines sales and profit growth; valuation uses P/E; technical recovery uses RSI, MACD, moving averages, volume, and support; correction uses drawdown from the highest Yahoo adjusted close in the available one-year history; risk/governance combines debt/equity with available promoter holding and pledging data.

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

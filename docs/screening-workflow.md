# Screening workflow

## Data workflow options

The application supports both the existing four-export Screener.in workflow and a free/hybrid workflow that uses one broad Screener.in fundamentals export. In either mode, the application downloads the Nifty 500 universe and Yahoo Finance price history, then evaluates the strategy rules locally.

### Free/hybrid: one fundamentals export

1. In Screener.in, prepare one broad export that includes the stocks you want considered. A broad filter such as `Market Capitalization > 0` can be used; the application's strategy-specific market-cap limits are still applied locally.
2. Export the financial fields used by the strategies: Symbol (or company name), Market Capitalization, ROCE, ROE, Debt to Equity, 3-year Sales Growth, 3-year Profit Growth, 3-year Operating Cash Flow, Promoter Holding, P/E, and Quarterly Sales/Profit Growth for Strategy 4.
3. Ensure the export identifies the statements as `Consolidated` with a `Statement Type` or `Financial Basis` column. Financial Period and Publication Date are recommended for traceability and historical backtesting.
4. Save the file as `data\inputs\fundamentals.csv` and run:

```powershell
python app.py `
  --fundamentals-csv data\inputs\fundamentals.csv `
  --output screening_results.xlsx
```

The app maps the export to the Nifty 500 universe, fetches available Yahoo Finance prices, calculates all four strategy memberships locally, and produces the workbook, result CSVs, and SQLite snapshot. This reduces the recurring export work to one file; fundamentals still need to be refreshed manually. Missing values are left unavailable rather than estimated.

### Existing Screener workflow: four strategy exports

1. Run each documented Screener.in strategy query and export its consolidated results.
2. Save the files as `data\inputs\strategy1.csv` through `data\inputs\strategy4.csv`.
3. Run:

```powershell
python app.py `
  --strategy-1 data\inputs\strategy1.csv `
  --strategy-2 data\inputs\strategy2.csv `
  --strategy-3 data\inputs\strategy3.csv `
  --strategy-4 data\inputs\strategy4.csv `
  --output screening_results.xlsx
```

Both workflows generate four individual screen result sheets and a `Final_Ranking` sheet. The application writes one result CSV per strategy and `Final_Ranking.csv` under `strategy_results\` by default, and stores a timestamped snapshot in the configured SQLite database.

## Ranking and review

The final ranking uses shared component weights of 20/20/15/20/15/10 for fundamental quality, earnings growth, valuation attractiveness, technical strength, recovery potential, and risk/governance. Multiple strategy memberships are shown as corroboration but do not add points. Review score coverage, financial publication dates, price dates, data quality, and company filings. Fair value and trade-level outputs remain unavailable until their methodology is specified.

Yahoo Finance prices and technical indicators may be unavailable for some symbols or have different as-of dates from the fundamentals. Screener exports are manual; the application does not log in to or scrape Screener.in. The `run_daily_screening.ps1` helper currently supports the four-export workflow and requires all four files to be refreshed on the current date. See the repository [README](../README.md) for setup, detailed field requirements, single-strategy usage, and output details.

# Screening workflow

## Recommended sequence

1. Run each documented query in Screener.in and export its consolidated results to CSV.
2. The local strategy runner validates each CSV against its strategy rule; Yahoo Finance supplies current price and technicals.
3. Consolidate matching stocks by ISIN and retain their membership across the four screens.
4. Score each screen and calculate the final ranking using the shared 20/20/15/20/15/10 component weights.
5. Review the top-ranked unique candidates, component coverage, risk/governance data, and source freshness.

The workbook contains four individual screen result sheets and a `Final_Ranking` sheet. Every run stores a timestamped snapshot in the shared SQLite database. After refreshing the four Screener exports, `run_daily_screening.ps1` runs the workflow and validates the input file dates. Configure Windows Task Scheduler to call it after market close if unattended execution is desired; Screener exports themselves remain a manual step.

Multiple strategy memberships are reported as corroboration but do not add points to the common final score. Fair-value and trade-level outputs remain unavailable until their methodology is specified. See the repository [README](../README.md) for commands, fields, and input requirements.
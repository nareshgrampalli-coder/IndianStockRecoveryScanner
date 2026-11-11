# Screening workflow

## Recommended sequence

1. Run all four screens and export each result to CSV.
2. Combine the results and remove duplicates to create a master Nifty 500 watchlist.
3. Score fundamentals: ROCE, ROE, sales growth, earnings growth, debt, cash flow, and valuation.
4. Score technical recovery: RSI, MACD, 20/50/200-day moving averages, volume, and support.
5. Rank candidates and select the best 10–15 for detailed research.

Export the resulting ranked watchlist to Excel with `python app.py`, then open the stock list and final-results dashboard with `python dashboard.py`. See the repository [README](../README.md) for the full commands and required input format.

Use Strategy 3 as the primary screen, Strategy 1 as the quality filter, and Strategy 4 as the entry-timing filter. This combination helps avoid selecting companies only because they are cheap or oversold.
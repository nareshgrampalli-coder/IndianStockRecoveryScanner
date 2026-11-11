# Strategy 1: Quality correction

## Quality and value

Find profitable companies with strong returns on capital, manageable debt and meaningful price corrections.

### Screener.in query

```text
Market Capitalization > 1000
AND Return on capital employed > 15
AND Return on equity > 15
AND Debt to equity < 0.5
AND Sales growth 3Years > 10
AND Profit growth 3Years > 10
AND Operating cash flow 3years > 0
AND Promoter holding > 35
AND Price to Earning < 35
AND Current price < High price * 0.75
```

### What it finds

- Companies with at least 25% drawdown.
- Strong historical profitability.
- Positive operating cash flow.
- Reasonable valuation.
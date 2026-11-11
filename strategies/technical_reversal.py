def matches(row) -> bool:
    return (
        row.get("market_cap", float("nan")) > 1000
        and row.get("52_week_high", float("nan")) > 0
        and row.get("market_price", float("nan"))
        < row.get("52_week_high", float("nan")) * 0.8
        and row.get("roce", float("nan")) > 12
        and row.get("debt_equity", float("nan")) < 0.7
        and row.get("sales_growth", float("nan")) > 5
        and row.get("profit_growth", float("nan")) > 5
        and row.get("quarterly_profit_growth", float("nan")) > 0
        and row.get("pe", float("nan")) < 35
        and 30 <= row.get("rsi14", float("nan")) <= 45
        and row.get("macd_bullish") is True
        and row.get("above_ema20") is True
        and row.get("volume_ratio_20d", float("nan")) >= 1.5
    )

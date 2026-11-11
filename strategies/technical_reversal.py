def matches(row) -> bool:
    return (
        30 <= row.get("rsi14", float("nan")) <= 45
        and row.get("macd_bullish") is True
        and row.get("above_sma20") is True
        and row.get("volume_ratio_20d", float("nan")) >= 1.5
    )

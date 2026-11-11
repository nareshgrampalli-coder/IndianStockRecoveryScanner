import pandas as pd


def score_technicals(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["rsi_score"] = frame["rsi14"].map(
        lambda x: 100 if 30 <= x <= 45 else 75 if 45 < x <= 60 else 50 if 25 <= x < 30 else 25
        if pd.notna(x) else float("nan")
    )
    frame["macd_score"] = frame["macd_bullish"].map(
        lambda x: 100 if x is True or str(x).lower() == "true" else 0
        if x is False or str(x).lower() == "false" else float("nan")
    )
    ma_cols = ["above_sma20", "above_sma50", "above_sma200"]
    frame["moving_average_score"] = frame[ma_cols].apply(
        lambda row: row.map(lambda x: 100 if x is True or str(x).lower() == "true" else 0
                            if x is False or str(x).lower() == "false" else float("nan")).mean(),
        axis=1,
    )
    frame["volume_score"] = frame["volume_ratio_20d"].map(
        lambda x: 100 if x >= 1.5 else 75 if x >= 1 else 25 if pd.notna(x) else float("nan")
    )
    frame["support_score"] = frame.apply(
        lambda r: 100 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d"))
        and r["market_price"] <= r["support_20d"] * 1.05 else
        75 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d"))
        and r["market_price"] <= r["support_20d"] * 1.10 else
        25 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d")) else float("nan"),
        axis=1,
    )
    components = ["rsi_score", "macd_score", "moving_average_score", "volume_score", "support_score"]
    frame["technical_score"] = frame[components].mean(axis=1, skipna=True)
    frame["technical_available"] = frame[components].notna().sum(axis=1)
    return frame

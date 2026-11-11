"""Normalize OHLCV price data."""

import pandas as pd


def clean_prices(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip().lower().replace(" ", "_") for column in result.columns]
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(result.columns)
    if missing:
        raise ValueError(f"OHLCV data is missing columns: {', '.join(sorted(missing))}")
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["open", "high", "low", "close"])
    result = result[result["high"] >= result["low"]]
    return result.sort_index()

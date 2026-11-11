"""Validation for normalized market and fundamentals data."""

import pandas as pd


def validate_prices(frame: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Price data is missing columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Price data is empty")
    if (frame["volume"].dropna() < 0).any():
        raise ValueError("Price data contains negative volume")
    adjusted = {f"adjusted_{column}" for column in ("open", "high", "low", "close")}
    if adjusted.intersection(frame.columns) and not adjusted.issubset(frame.columns):
        raise ValueError("Price data must retain all raw and adjusted OHLC values")
    if adjusted.issubset(frame.columns) and frame[list(adjusted)].isna().any().any():
        raise ValueError("Adjusted OHLC data contains missing values")

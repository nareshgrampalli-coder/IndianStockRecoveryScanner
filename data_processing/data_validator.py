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

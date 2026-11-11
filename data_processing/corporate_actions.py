"""Corporate-action adjustment boundary."""

import pandas as pd


def apply_adjustments(prices: pd.DataFrame, adjustments: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return provider-adjusted prices; raw action data needs provider-specific semantics."""
    if adjustments is not None and not adjustments.empty:
        raise NotImplementedError(
            "Corporate-action adjustment formats vary by exchange; supply adjusted OHLCV from the provider."
        )
    return prices.copy()

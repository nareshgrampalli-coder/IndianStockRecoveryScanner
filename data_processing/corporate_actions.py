"""Preserve raw OHLC and calculate split/dividend-adjusted OHLC from provider data."""

import pandas as pd

from data_processing.price_cleaner import clean_prices


def apply_adjustments(
    prices: pd.DataFrame,
    adjustments: pd.DataFrame | None = None,
    adjusted_close: pd.Series | None = None,
) -> pd.DataFrame:
    """Derive adjusted OHLC using the provider's adjusted-close/raw-close factor."""
    raw = clean_prices(prices)
    if adjusted_close is None:
        if "adj_close" not in raw:
            raise ValueError(
                "Adjusted close is required to adjust OHLC for corporate actions; "
                "request provider data with auto-adjust disabled and adjusted close included."
            )
        adjusted_close = raw["adj_close"]
    if adjustments is not None and not adjustments.empty:
        raise NotImplementedError(
            "Explicit corporate-action schedules are not yet supported; use the provider's "
            "adjusted close so the adjustment factor is applied consistently."
        )
    adjusted_close = pd.to_numeric(adjusted_close, errors="coerce").reindex(raw.index)
    factor = adjusted_close / raw["close"].replace(0, float("nan"))
    if factor.isna().any() or (factor <= 0).any():
        raise ValueError("Corporate-action adjustment factors are missing or invalid")

    for column in ("open", "high", "low", "close"):
        raw[f"raw_{column}"] = raw[column]
        raw[f"adjusted_{column}"] = raw[column] * factor
        raw[column] = raw[f"adjusted_{column}"]
    raw["adjustment_factor"] = factor
    raw["adj_close"] = adjusted_close
    raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
    return raw

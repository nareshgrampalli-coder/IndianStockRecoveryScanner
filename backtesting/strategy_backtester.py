from collections.abc import Callable

import pandas as pd


def point_in_time_fundamentals(
    fundamentals: pd.DataFrame, as_of: object
) -> pd.DataFrame:
    """Return only consolidated observations whose period and publication were known by as_of."""
    required = {"financial_period", "publication_date", "financial_basis"}
    missing = required.difference(fundamentals.columns)
    if missing:
        raise ValueError(f"Point-in-time fundamentals require columns: {', '.join(sorted(missing))}")
    as_of_utc = pd.to_datetime(as_of, utc=True, errors="raise")
    period = pd.to_datetime(fundamentals["financial_period"], utc=True, errors="coerce")
    published = pd.to_datetime(fundamentals["publication_date"], utc=True, errors="coerce")
    basis = fundamentals["financial_basis"].astype("string").str.strip().str.lower()
    consolidated = basis.str.contains("consolidated", na=False) & ~basis.str.contains(
        "standalone", na=False
    )
    visible = (
        period.notna() & published.notna()
        & period.le(as_of_utc) & published.lt(as_of_utc)
        & consolidated
    )
    return fundamentals.loc[visible].copy()


def backtest(close: pd.Series, signal: pd.Series) -> pd.DataFrame:
    """Calculate next-bar long-only strategy returns and buy-and-hold returns."""
    if not close.index.equals(signal.index):
        raise ValueError("Close prices and signals must have matching indexes")
    returns = close.pct_change().fillna(0)
    position = signal.astype(bool).shift(1, fill_value=False)
    return pd.DataFrame({
        "strategy_return": returns.where(position, 0.0),
        "buy_hold_return": returns,
    }, index=close.index)


def backtest_with_fundamentals(
    close: pd.Series,
    fundamentals: pd.DataFrame,
    signal_builder: Callable[[pd.Series, pd.DataFrame], bool],
) -> pd.DataFrame:
    """Build signals from adjusted close and consolidated financials known by each session."""
    signals = pd.Series(False, index=close.index, dtype=bool)
    for session in close.index:
        available = point_in_time_fundamentals(fundamentals, session)
        signals.loc[session] = bool(
            signal_builder(close.loc[:session], available)
        )
    return backtest(close, signals)

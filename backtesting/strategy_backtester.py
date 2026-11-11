import pandas as pd


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

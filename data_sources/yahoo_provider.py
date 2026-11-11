"""Yahoo Finance secondary price-history provider."""

import pandas as pd
import yfinance as yf


class YahooProvider:
    def __init__(self, period: str = "1y", timeout: int = 20):
        self.period, self.timeout = period, timeout

    def history(self, symbol: str) -> pd.DataFrame:
        return yf.Ticker(f"{symbol}.NS").history(
            period=self.period, auto_adjust=False, actions=True,
            raise_errors=True, timeout=self.timeout
        )

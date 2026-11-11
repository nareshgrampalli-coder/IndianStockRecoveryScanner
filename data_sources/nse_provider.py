"""Public NSE Indices constituent data."""

from io import BytesIO
import warnings

import pandas as pd
import requests

from data_processing.financial_cleaner import normalize_header
from data_processing.security_master import is_valid_isin


class NSEProvider:
    def __init__(self, universe_url: str, timeout: int = 30):
        self.universe_url = universe_url
        self.timeout = timeout

    def nifty500(self) -> pd.DataFrame:
        response = requests.get(
            self.universe_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=self.timeout
        )
        response.raise_for_status()
        frame = pd.read_csv(BytesIO(response.content))
        columns = {normalize_header(column): column for column in frame.columns}
        symbol = next((columns[key] for key in ("symbol", "ticker") if key in columns), None)
        name = next((columns[key] for key in ("company name", "name") if key in columns), None)
        isin = next((columns[key] for key in ("isin code", "isin") if key in columns), None)
        if symbol is None:
            raise ValueError("NSE constituent file has no Symbol column")
        if isin is None:
            raise ValueError("NSE constituent file has no ISIN column; ISIN is required as the canonical identifier")
        result = pd.DataFrame({
            "symbol": frame[symbol].astype("string").str.strip().str.upper(),
            "isin": frame[isin].astype("string").str.strip().str.upper(),
        })
        result["symbol"] = result["symbol"].replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
        result["isin"] = result["isin"].replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
        result["nifty_name"] = (
            frame[name].astype("string").str.strip()
            if name else result["symbol"]
        )
        result["nifty_name"] = result["nifty_name"].fillna(result["symbol"])

        incomplete = result["symbol"].isna() | result["isin"].isna()
        if incomplete.any():
            rejected = result.loc[incomplete, ["symbol", "isin", "nifty_name"]]
            warnings.warn(
                f"Removing {len(rejected)} incomplete NSE constituent row(s): "
                f"{rejected.to_dict('records')}",
                RuntimeWarning,
                stacklevel=2,
            )
            result = result.loc[~incomplete].copy()

        valid_isin = result["isin"].map(is_valid_isin)
        if (~valid_isin).any():
            rejected = result.loc[~valid_isin, ["symbol", "isin", "nifty_name"]]
            warnings.warn(
                f"Removing {len(rejected)} NSE constituent row(s) with invalid ISINs: "
                f"{rejected.to_dict('records')}",
                RuntimeWarning,
                stacklevel=2,
            )
            result = result.loc[valid_isin].copy()

        duplicate_rows = result.duplicated(["symbol", "isin"], keep="first")
        if duplicate_rows.any():
            warnings.warn(
                f"Removing {int(duplicate_rows.sum())} duplicate NSE constituent row(s)",
                RuntimeWarning,
                stacklevel=2,
            )
            result = result.loc[~duplicate_rows].copy()
        if result["isin"].duplicated().any():
            duplicate_isins = result.loc[
                result["isin"].duplicated(keep=False), ["symbol", "isin"]
            ].to_dict("records")
            raise ValueError(f"NSE constituent file has ISINs mapped to multiple symbols: {duplicate_isins}")
        if result["symbol"].duplicated().any():
            duplicate_symbols = result.loc[
                result["symbol"].duplicated(keep=False), ["symbol", "isin"]
            ].to_dict("records")
            raise ValueError(f"NSE constituent file has symbols mapped to multiple ISINs: {duplicate_symbols}")
        if result.empty:
            raise ValueError("NSE constituent file has no rows with valid symbols and ISINs")

        result["nse_symbol"] = result["symbol"]
        result["bse_symbol"] = pd.NA
        return result[
            ["symbol", "isin", "nse_symbol", "bse_symbol", "nifty_name"]
        ].reset_index(drop=True)

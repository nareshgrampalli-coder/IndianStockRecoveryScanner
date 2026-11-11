"""Public NSE Indices constituent data."""

from io import BytesIO

import pandas as pd
import requests

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
        symbol = next((c for c in frame if str(c).strip().lower() in {"symbol", "ticker"}), None)
        name = next((c for c in frame if str(c).strip().lower() in {"company name", "name"}), None)
        isin = next((c for c in frame if str(c).strip().lower() in {"isin code", "isin"}), None)
        if symbol is None:
            raise ValueError("NSE constituent file has no Symbol column")
        if isin is None:
            raise ValueError("NSE constituent file has no ISIN column; ISIN is required as the canonical identifier")
        result = pd.DataFrame({
            "symbol": frame[symbol].astype(str).str.strip().str.upper(),
            "isin": frame[isin].astype(str).str.strip().str.upper(),
        })
        result["isin"] = result["isin"].replace({"NAN": "", "NONE": ""})
        result["nse_symbol"] = result["symbol"]
        result["bse_symbol"] = pd.NA
        result["nifty_name"] = frame[name] if name else result["symbol"]
        result = result[result["symbol"].ne("") & result["isin"].ne("")]
        invalid_isins = result.loc[~result["isin"].map(is_valid_isin), "isin"].tolist()
        if invalid_isins:
            raise ValueError(f"NSE constituent file contains invalid ISIN values: {invalid_isins}")
        if result["isin"].duplicated().any():
            raise ValueError("NSE constituent file has duplicate ISINs")
        return result.drop_duplicates("symbol").reset_index(drop=True)

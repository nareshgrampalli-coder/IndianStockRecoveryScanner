"""Public NSE Indices constituent data."""

from io import BytesIO

import pandas as pd
import requests


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
        if symbol is None:
            raise ValueError("NSE constituent file has no Symbol column")
        result = pd.DataFrame({"symbol": frame[symbol].astype(str).str.strip().str.upper()})
        result["nifty_name"] = frame[name] if name else result["symbol"]
        return result[result["symbol"].ne("")].drop_duplicates("symbol").reset_index(drop=True)

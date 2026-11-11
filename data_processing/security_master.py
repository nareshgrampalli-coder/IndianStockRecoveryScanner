"""Load and reconcile canonical ISIN-to-exchange-symbol mappings."""

from pathlib import Path
import re

import pandas as pd

from data_processing.financial_cleaner import normalize_header

ISIN_PATTERN = re.compile(r"^IN[A-Z0-9]{9}[0-9]$")


def is_valid_isin(value: object) -> bool:
    return bool(ISIN_PATTERN.fullmatch(str(value).strip().upper()))


def load_security_mappings(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=["isin", "company_name", "nse_symbol", "bse_symbol"])
    frame = pd.read_csv(path, dtype="string")
    frame.columns = [normalize_header(column).replace(" ", "_") for column in frame.columns]
    required = {"isin", "nse_symbol", "bse_symbol"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path}: security mapping file is missing columns: {', '.join(sorted(missing))}")
    if "company_name" not in frame:
        frame["company_name"] = pd.NA
    for column in ("isin", "nse_symbol", "bse_symbol"):
        frame[column] = frame[column].astype("string").str.strip().str.upper()
        frame[column] = frame[column].replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    frame = frame.dropna(subset=["isin"])
    if frame["isin"].duplicated().any():
        raise ValueError(f"{path}: ISIN must be unique in the security mapping file")
    invalid = frame.loc[~frame["isin"].map(is_valid_isin), "isin"].tolist()
    if invalid:
        raise ValueError(f"{path}: invalid Indian ISIN value(s): {invalid}")
    return frame[["isin", "company_name", "nse_symbol", "bse_symbol"]]


def apply_security_mappings(universe: pd.DataFrame, mappings: pd.DataFrame) -> pd.DataFrame:
    result = universe.copy()
    if mappings.empty:
        return result
    by_isin = mappings.set_index("isin")
    result = result.set_index("isin", drop=False)
    for field in ("nse_symbol", "bse_symbol", "nifty_name"):
        mapping_field = "company_name" if field == "nifty_name" else field
        if mapping_field not in by_isin:
            continue
        values = by_isin[mapping_field].reindex(result.index)
        result[field] = values.combine_first(result[field])
    result["symbol"] = result["nse_symbol"].combine_first(result["symbol"])
    return result.reset_index(drop=True)

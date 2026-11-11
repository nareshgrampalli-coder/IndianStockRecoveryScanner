"""Import and normalize Screener.in CSV exports."""

from pathlib import Path

import pandas as pd

from data_processing.financial_cleaner import normalize_header, number

ALIASES = {
    "symbol": ("symbol", "ticker", "nse symbol", "stock"),
    "name": ("name", "company", "company name"),
    "roce": ("roce", "return on capital employed"),
    "roe": ("roe", "return on equity"),
    "sales_growth": ("sales growth", "sales growth 3years", "sales growth 5years"),
    "profit_growth": ("profit growth", "profit growth 3years", "profit growth 5years", "earnings growth"),
    "debt_equity": ("debt to equity", "debt/equity", "debt equity"),
    "operating_cash_flow": ("operating cash flow 3years", "operating cash flow", "cash from operating activity"),
    "pe": ("stock p/e", "price to earning", "price to earnings", "p/e", "pe"),
    "market_cap": ("market cap rs.cr.", "market capitalization", "market cap"),
}


def find_column(frame: pd.DataFrame, field: str) -> str | None:
    normalized = {normalize_header(col): col for col in frame.columns}
    aliases = [normalize_header(alias) for alias in ALIASES[field]]
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return next(
        (original for header, original in normalized.items()
         for alias in aliases if alias and alias in header),
        None,
    )


def read_screener(path: str | Path, strategy: str) -> pd.DataFrame:
    path = Path(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    symbol_col, name_col = find_column(frame, "symbol"), find_column(frame, "name")
    if symbol_col is None and name_col is None:
        raise ValueError(f"{path}: expected a Symbol, Ticker, or company Name column")
    rows = pd.DataFrame(index=frame.index)
    rows["symbol"] = frame[symbol_col] if symbol_col else ""
    rows["name"] = frame[name_col] if name_col else frame[symbol_col]
    rows["symbol"] = rows["symbol"].astype(str).str.strip().str.upper()
    rows.loc[rows["symbol"].isin(("", "NAN", "NONE")), "symbol"] = ""
    rows["name"] = rows["name"].astype(str).str.strip()
    rows["strategy"] = strategy
    for field in ("roce", "roe", "sales_growth", "profit_growth", "debt_equity",
                  "operating_cash_flow", "pe", "market_cap"):
        column = find_column(frame, field)
        rows[field] = frame[column].map(number) if column else float("nan")
    return rows[rows["symbol"].eq("") | rows["symbol"].str.match(r"^[A-Z0-9&.-]+$", na=False)]

"""Import and normalize Screener.in CSV exports."""

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from data_processing.financial_cleaner import normalize_header, number
from data_processing.security_master import is_valid_isin

ALIASES = {
    "symbol": ("symbol", "ticker", "nse symbol", "stock"),
    "name": ("name", "company", "company name"),
    "roce": ("roce", "return on capital employed"),
    "roe": ("roe", "return on equity"),
    "sales_growth": ("sales growth", "sales growth 3years", "sales growth 5years"),
    "profit_growth": ("profit growth", "profit growth 3years", "profit growth 5years", "earnings growth"),
    "quarterly_sales_growth": ("quarterly sales growth", "sales growth qtr"),
    "quarterly_profit_growth": ("quarterly profit growth", "profit growth qtr"),
    "debt_equity": ("debt to equity", "debt/equity", "debt equity"),
    "operating_cash_flow": ("operating cash flow 3years", "operating cash flow", "cash from operating activity"),
    "pe": ("stock p/e", "price to earning", "price to earnings", "p/e", "pe"),
    "market_cap": ("market cap rs.cr.", "market capitalization", "market cap"),
    "promoter_holding": ("promoter holding", "promoters holding"),
    "promoter_pledging": ("pledged percentage", "promoter pledged", "promoter pledging"),
    "isin": ("isin", "isin code"),
    "financial_basis": (
        "financial basis", "financial statement basis", "statement type",
        "consolidation", "consolidated standalone",
    ),
    "financial_period": ("financial period", "period ended", "financial year", "quarter ended"),
    "publication_date": ("publication date", "filing date", "published on", "announcement date"),
    "data_provider": ("data provider", "source", "provider"),
}


def find_column(frame: pd.DataFrame, field: str) -> str | None:
    normalized = {normalize_header(col): col for col in frame.columns}
    if field in {"sales_growth", "profit_growth"}:
        normalized = {
            header: original for header, original in normalized.items()
            if not header.startswith("quarterly ")
        }
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
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError as exc:
        raise ValueError(
            f"{path}: Screener CSV is empty; export the strategy results with headers and data rows"
        ) from exc
    if frame.empty:
        raise ValueError(f"{path}: Screener CSV contains headers but no data rows")
    symbol_col, name_col = find_column(frame, "symbol"), find_column(frame, "name")
    basis_col = find_column(frame, "financial_basis")
    if symbol_col is None and name_col is None:
        raise ValueError(f"{path}: expected a Symbol, Ticker, or company Name column")
    if basis_col is None:
        raise ValueError(
            f"{path}: missing financial statement basis; add a Financial Basis or Statement Type column "
            "with consolidated values"
        )
    basis = frame[basis_col].astype("string").str.strip().str.lower()
    consolidated = basis.str.contains("consolidated", na=False) & ~basis.str.contains(
        "standalone", na=False
    )
    if not consolidated.all():
        invalid = sorted(basis[~consolidated].dropna().unique().tolist())
        raise ValueError(
            f"{path}: only consolidated financial statements are accepted; "
            f"invalid/missing basis values: {invalid}"
        )
    rows = pd.DataFrame(index=frame.index)
    rows["symbol"] = frame[symbol_col] if symbol_col else ""
    rows["name"] = frame[name_col] if name_col else frame[symbol_col]
    rows["symbol"] = rows["symbol"].astype(str).str.strip().str.upper()
    rows.loc[rows["symbol"].isin(("", "NAN", "NONE")), "symbol"] = ""
    rows["name"] = rows["name"].astype(str).str.strip()
    rows["strategy"] = strategy
    isin_col = find_column(frame, "isin")
    rows["isin"] = frame[isin_col].astype("string").str.strip().str.upper() if isin_col else pd.NA
    rows["isin"] = rows["isin"].replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA})
    invalid_isins = rows.loc[rows["isin"].notna() & ~rows["isin"].map(
        lambda value: pd.isna(value) or is_valid_isin(value)
    ), "isin"].tolist()
    if invalid_isins:
        raise ValueError(f"{path}: invalid ISIN value(s): {invalid_isins}")
    rows["financial_basis"] = "consolidated"
    for field in ("financial_period", "publication_date"):
        column = find_column(frame, field)
        rows[field] = frame[column].astype("string").str.strip() if column else pd.NA
    provider_col = find_column(frame, "data_provider")
    rows["data_provider"] = (
        frame[provider_col].astype("string").str.strip()
        if provider_col else "Screener.in"
    )
    rows["data_provider"] = rows["data_provider"].replace(
        {"": "Screener.in", "nan": "Screener.in", "None": "Screener.in"}
    )
    rows["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
    for field in ("roce", "roe", "sales_growth", "profit_growth",
                  "quarterly_sales_growth", "quarterly_profit_growth", "debt_equity",
                  "operating_cash_flow", "pe", "market_cap", "promoter_holding",
                  "promoter_pledging"):
        column = find_column(frame, field)
        rows[field] = frame[column].map(number) if column else float("nan")
    quality_fields = [
        "roce", "roe", "sales_growth", "profit_growth", "debt_equity",
        "quarterly_sales_growth", "quarterly_profit_growth",
        "operating_cash_flow", "pe", "market_cap", "promoter_holding",
        "promoter_pledging", "financial_period", "publication_date",
    ]
    rows["data_quality_score"] = rows[quality_fields].notna().mean(axis=1) * 100
    missing = rows[quality_fields].isna()
    rows["financial_data_missing_fields"] = missing.apply(
        lambda values: ", ".join(values.index[values].tolist()), axis=1
    )
    return rows[rows["symbol"].eq("") | rows["symbol"].str.match(r"^[A-Z0-9&.-]+$", na=False)]

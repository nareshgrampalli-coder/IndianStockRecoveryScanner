"""Build a normalized, provider-independent Nifty 500 ingestion dataset."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol

import pandas as pd

from data_processing.corporate_actions import apply_adjustments
from data_processing.data_validator import validate_prices
from data_processing.financial_cleaner import normalize_company, normalize_header, number
from data_processing.price_cleaner import clean_prices
from data_processing.security_master import apply_security_mappings, load_security_mappings
from data_sources.screener_importer import read_screener
from database.models import FundamentalObservation, PriceBar, SecurityMapping
from database.repository import ScreeningRepository

STRATEGIES = ("strategy_1", "strategy_2", "strategy_3", "strategy_4")
FINANCIAL_FIELDS = (
    "roce", "roe", "sales_growth", "profit_growth",
    "quarterly_sales_growth", "quarterly_profit_growth", "debt_equity",
    "operating_cash_flow", "pe", "market_cap", "promoter_holding",
    "promoter_pledging",
)
AGGREGATE_FIELDS = (
    "name", *FINANCIAL_FIELDS, "financial_basis", "financial_period",
    "publication_date", "data_provider", "retrieved_at_utc",
    "data_quality_score", "financial_data_missing_fields",
)
RAW_OHLC = ("raw_open", "raw_high", "raw_low", "raw_close")
ADJUSTED_OHLC = (
    "adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close",
)
QUALITY_FIELDS = (*RAW_OHLC, *ADJUSTED_OHLC, "volume", "adjustment_factor")


class DailyPriceProvider(Protocol):
    name: str

    def history(self, symbol: str) -> pd.DataFrame: ...


def combine_strategy_exports(
    universe: pd.DataFrame,
    paths: dict[str, str | Path],
) -> pd.DataFrame:
    """Join the four consolidated Screener exports onto the full index universe."""
    imported = pd.concat(
        [read_screener(paths[strategy], strategy) for strategy in STRATEGIES],
        ignore_index=True,
    )
    isin_to_symbol = dict(zip(universe["isin"], universe["symbol"]))
    symbols = set(universe["symbol"])
    name_to_symbol = {
        normalize_company(name): symbol
        for name, symbol in zip(universe["nifty_name"], universe["symbol"])
    }

    def map_symbol(row):
        if pd.notna(row["isin"]):
            return isin_to_symbol.get(row["isin"], "")
        if row["symbol"] in symbols:
            return row["symbol"]
        return name_to_symbol.get(normalize_company(row["name"]), "")

    imported["symbol"] = imported.apply(map_symbol, axis=1)
    imported = imported[imported["symbol"].ne("")].copy()
    if not imported.empty:
        imported["_publication_sort"] = pd.to_datetime(
            imported["publication_date"], errors="coerce", utc=True
        )
        imported["_period_sort"] = pd.to_datetime(
            imported["financial_period"], errors="coerce", utc=True
        )
        imported = imported.sort_values(
            ["_publication_sort", "_period_sort"],
            ascending=False,
            na_position="last",
        )
        imported = imported.groupby("symbol", as_index=False).agg(
            {
                **{field: "first" for field in AGGREGATE_FIELDS},
                "strategy": lambda values: ", ".join(sorted(set(values))),
            }
        )

    stocks = universe.merge(imported, on="symbol", how="left")
    stocks["strategy_membership"] = stocks["strategy"].fillna("")
    for strategy in STRATEGIES:
        stocks[f"{strategy}_member"] = stocks["strategy_membership"].str.split(", ").map(
            lambda members: strategy in members
        )
    missing_columns = [
        column for column in FINANCIAL_FIELDS if column not in stocks.columns
    ]
    for column in missing_columns:
        stocks[column] = float("nan")
    missing_metrics = stocks[list(FINANCIAL_FIELDS)].isna()
    metric_missing = missing_metrics.apply(
        lambda values: values.index[values].tolist(), axis=1
    )
    existing_missing = stocks["financial_data_missing_fields"].fillna("").str.split(", ")

    def missing_fields(index):
        fields = set(existing_missing.loc[index]) - {""}
        fields.update(metric_missing.loc[index])
        if stocks.at[index, "strategy"] is pd.NA or pd.isna(stocks.at[index, "strategy"]):
            fields.update(FINANCIAL_FIELDS)
            fields.update(("financial_period", "publication_date", "financial_basis"))
        return ", ".join(sorted(fields))

    stocks["financial_data_missing_fields"] = [
        missing_fields(index) for index in stocks.index
    ]
    stocks["financial_data_quality_score"] = stocks["data_quality_score"].fillna(0)
    stocks["financial_basis"] = stocks["financial_basis"].fillna("unavailable")
    stocks["financial_data_provider"] = stocks["data_provider"].fillna("unavailable")
    return stocks.drop(columns=["strategy", "data_provider"], errors="ignore")


def normalize_price_history(
    isin: str,
    symbol: str,
    history: pd.DataFrame,
    provider_name: str,
    retrieved_at_utc: str,
) -> tuple[pd.DataFrame, list[PriceBar]]:
    prices = apply_adjustments(clean_prices(history))
    validate_prices(prices)
    prices = prices.copy()
    prices["isin"] = isin
    prices["symbol"] = symbol
    prices["provider"] = provider_name
    prices["retrieved_at_utc"] = retrieved_at_utc
    prices["session_date"] = prices.index.strftime("%Y-%m-%d")
    prices["data_quality_score"] = prices[list(QUALITY_FIELDS)].notna().mean(axis=1) * 100
    price_bars = [
        PriceBar(
            isin=isin,
            session_date=index.strftime("%Y-%m-%d"),
            provider=provider_name,
            retrieved_at_utc=retrieved_at_utc,
            data_quality_score=float(row["data_quality_score"]),
            raw_open=float(row["raw_open"]),
            raw_high=float(row["raw_high"]),
            raw_low=float(row["raw_low"]),
            raw_close=float(row["raw_close"]),
            adjusted_open=float(row["adjusted_open"]),
            adjusted_high=float(row["adjusted_high"]),
            adjusted_low=float(row["adjusted_low"]),
            adjusted_close=float(row["adjusted_close"]),
            volume=float(row["volume"]) if pd.notna(row["volume"]) else None,
            adjustment_factor=float(row["adjustment_factor"]),
        )
        for index, row in prices.iterrows()
    ]
    return prices, price_bars


def load_nse_bhavcopy(path: str | Path) -> pd.DataFrame:
    """Read an NSE bhavcopy CSV with ISIN, trade date, and closing price columns."""
    source = pd.read_csv(path, dtype="string")
    source.columns = [normalize_header(column).replace(" ", "_") for column in source.columns]

    def find(*aliases: str) -> str | None:
        return next((alias for alias in aliases if alias in source.columns), None)

    isin_col = find("isin", "isin_code")
    date_col = find("trade_date", "trading_date", "trad_dt", "trad_dt_", "traddt")
    close_col = find("close", "close_price", "cls_pric", "clspric")
    missing = [
        name for name, value in (
            ("ISIN", isin_col), ("trade date", date_col), ("close price", close_col)
        ) if value is None
    ]
    if missing:
        raise ValueError(f"{path}: bhavcopy is missing required columns: {', '.join(missing)}")
    result = pd.DataFrame({
        "isin": source[isin_col].str.strip().str.upper(),
        "bhavcopy_session_date": pd.to_datetime(source[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
        "nse_bhavcopy_close": source[close_col].map(number),
    })
    result = result.dropna(subset=["isin", "bhavcopy_session_date", "nse_bhavcopy_close"])
    return result.drop_duplicates(["isin", "bhavcopy_session_date"], keep="last")


def validate_latest_prices(stocks: pd.DataFrame, prices: pd.DataFrame, bhavcopy: pd.DataFrame) -> pd.DataFrame:
    result = stocks.copy()
    if prices.empty:
        result["price_validation_status"] = "NO_PROVIDER_PRICE"
        return result
    latest = prices.sort_values("session_date").groupby("isin", as_index=False).tail(1)
    latest = latest[["isin", "session_date", "raw_close"]].rename(
        columns={"session_date": "price_asof", "raw_close": "provider_raw_close"}
    )
    result = result.merge(latest, on="isin", how="left")
    result["price_validation_status"] = "NOT_PROVIDED"
    result["nse_bhavcopy_close"] = float("nan")
    result["price_validation_diff_pct"] = float("nan")
    if bhavcopy.empty:
        return result
    result = result.drop(
        columns=["price_validation_status", "nse_bhavcopy_close", "price_validation_diff_pct"]
    ).merge(bhavcopy, left_on=["isin", "price_asof"],
            right_on=["isin", "bhavcopy_session_date"], how="left")
    result["price_validation_diff_pct"] = (
        (result["provider_raw_close"] - result["nse_bhavcopy_close"])
        / result["nse_bhavcopy_close"] * 100
    )
    result["price_validation_status"] = "NO_SESSION_MATCH"
    found = result["nse_bhavcopy_close"].notna()
    result.loc[found & result["price_validation_diff_pct"].abs().le(0.5),
               "price_validation_status"] = "MATCH"
    result.loc[found & result["price_validation_diff_pct"].abs().gt(0.5),
               "price_validation_status"] = "MISMATCH"
    return result


def run_ingestion(
    universe_provider,
    price_provider: DailyPriceProvider,
    strategy_paths: dict[str, str | Path],
    settings: dict,
    output_dir: str | Path,
    bhavcopy_path: str | Path | None = None,
) -> dict[str, Path]:
    """Ingest all index constituents, strategy exports, and daily history."""
    universe = universe_provider.nifty500()
    universe = apply_security_mappings(
        universe, load_security_mappings(settings["security_master_path"])
    )
    stocks = combine_strategy_exports(universe, strategy_paths)
    bhavcopy = load_nse_bhavcopy(bhavcopy_path) if bhavcopy_path else pd.DataFrame()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    all_prices: list[pd.DataFrame] = []
    price_bars: list[PriceBar] = []
    errors: list[dict] = []

    def fetch(row):
        history = price_provider.history(row.symbol)
        return normalize_price_history(
            row.isin, row.symbol, history,
            getattr(price_provider, "name", price_provider.__class__.__name__),
            datetime.now(timezone.utc).isoformat(),
        )

    with ThreadPoolExecutor(max_workers=settings["technical_workers"]) as executor:
        futures = {
            executor.submit(fetch, row): row
            for row in universe.itertuples(index=False)
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                normalized, bars = future.result()
            except Exception as exc:
                errors.append({
                    "isin": row.isin, "symbol": row.symbol,
                    "error": str(exc)[:240], "retrieved_at_utc": retrieved_at,
                })
                continue
            all_prices.append(normalized.reset_index(drop=True))
            price_bars.extend(bars)

    price_frame = pd.concat(all_prices, ignore_index=True) if all_prices else pd.DataFrame()
    stocks = validate_latest_prices(stocks, price_frame, bhavcopy)
    if not price_frame.empty:
        latest_metrics = price_frame.sort_values("session_date").groupby("isin").tail(1).set_index("isin")
        for target, source in (
            ("market_price", "close"), ("price_data_quality_score", "data_quality_score"),
            ("price_provider", "provider"), ("price_retrieved_at_utc", "retrieved_at_utc"),
        ):
            stocks[target] = stocks["isin"].map(latest_metrics[source])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "stocks": output_dir / "normalized_stocks.csv",
        "prices": output_dir / "normalized_daily_prices.csv",
        "errors": output_dir / "ingestion_errors.csv",
    }
    stocks.to_csv(paths["stocks"], index=False)
    price_frame.to_csv(paths["prices"], index=False)
    pd.DataFrame(errors, columns=["isin", "symbol", "error", "retrieved_at_utc"]).to_csv(
        paths["errors"], index=False
    )
    if price_frame.empty:
        raise RuntimeError(
            f"No price history was successfully normalized; see {paths['errors']}"
        )

    securities = [
        SecurityMapping(
            isin=row.isin,
            company_name=str(row.nifty_name),
            nse_symbol=str(row.nse_symbol) if pd.notna(row.nse_symbol) else None,
            bse_symbol=str(row.bse_symbol) if pd.notna(row.bse_symbol) else None,
        )
        for row in universe.itertuples(index=False)
    ]
    financial_records = []
    for row in stocks.itertuples(index=False):
        if row.financial_basis != "consolidated":
            continue
        payload = {
            field: (None if pd.isna(getattr(row, field)) else getattr(row, field))
            for field in (*FINANCIAL_FIELDS, "financial_data_missing_fields")
        }
        financial_records.append(FundamentalObservation(
            isin=row.isin,
            financial_period=None if pd.isna(row.financial_period) else str(row.financial_period),
            publication_date=None if pd.isna(row.publication_date) else str(row.publication_date),
            financial_basis=row.financial_basis,
            data_provider=row.financial_data_provider,
            retrieved_at_utc=str(row.retrieved_at_utc),
            data_quality_score=float(row.financial_data_quality_score),
            payload=json.dumps(payload, default=str),
        ))
    ScreeningRepository(settings["database_path"]).save_market_data(
        securities, price_bars, financial_records
    )
    return paths

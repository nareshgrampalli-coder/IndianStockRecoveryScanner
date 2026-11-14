"""Build a provisional ranking from copied Screener query tables."""

from collections import defaultdict
from pathlib import Path
import re
import statistics

import pandas as pd

from data_processing.financial_cleaner import normalize_company, normalize_header, number
from scoring.weighted_score import score_price_correction

STRATEGY_SOURCES = {
    "quality_correction": ("quality_correction.csv", "quality_correction_results.csv"),
    "deep_value": ("deep_value.csv", "deep_value_results.csv"),
    "recovery_30_50": ("recovery_30_50.csv", "recovery_30_50_results.csv"),
    "technical_reversal": ("technical_reversal.csv", "technical_reversal_results.csv"),
}
ALIASES = {
    "company": ("company", "company name", "name", "stock"),
    "symbol": ("symbol", "nse symbol", "ticker"),
    "isin": ("isin", "isin code"),
    "market_price": ("cmp rs", "current price", "market price"),
    "market_cap": (
        "mar cap rs cr", "market cap rs cr", "market capitalization", "market cap",
    ),
    "pe": ("p e", "stock p e", "pe", "price to earnings"),
    "roce": ("roce", "roce percent"),
    "roe": ("roe", "roe percent"),
    "quarterly_sales_growth": ("qtr sales var", "quarterly sales growth"),
    "quarterly_profit_growth": ("qtr profit var", "quarterly profit growth"),
    "52_week_high": ("52w high rs", "52 week high", "price high 1y"),
    "sales_growth": ("sales growth 3years", "sales growth"),
    "profit_growth": ("profit growth 3years", "profit growth"),
    "debt_equity": ("debt to equity", "debt equity"),
    "operating_cash_flow": ("operating cash flow 3years", "operating cash flow"),
    "promoter_holding": ("promoter holding", "promoters holding"),
    "rsi14": ("rsi14", "rsi"),
    "volume_ratio_20d": ("volume ratio 20d", "volume ratio"),
}
NUMERIC_FIELDS = (
    "market_price", "market_cap", "pe", "roce", "roe",
    "quarterly_sales_growth", "quarterly_profit_growth", "52_week_high",
    "sales_growth", "profit_growth", "debt_equity", "operating_cash_flow",
    "promoter_holding", "rsi14", "volume_ratio_20d",
)
WEIGHTS = {
    "business_quality_score": 30,
    "quarterly_growth_score": 30,
    "valuation_score": 20,
    "price_correction_score": 20,
}


def _company_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", normalize_company(value))
    return {
        "natlaluminium": "nationalaluminium",
    }.get(key, key)


def _read_table(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Screener table not found: {path}")
    if path.stat().st_size == 0:
        return _empty_table(path)
    try:
        frame = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return _empty_table(path)
    except pd.errors.ParserError as exc:
        raise ValueError(f"Could not parse copied Screener table: {path}: {exc}") from exc
    if frame.empty and len(frame.columns) == 0:
        raise ValueError(f"Screener table has no headers: {path}")

    normalized = {normalize_header(column): column for column in frame.columns}
    columns = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            header = normalize_header(alias)
            if header in normalized:
                columns[field] = normalized[header]
                break
    if "company" not in columns:
        raise ValueError(f"{path}: expected a Company or Name column")

    rows = pd.DataFrame(index=frame.index)
    for field in ("company", "symbol", "isin"):
        column = columns.get(field)
        rows[field] = frame[column].astype("string").str.strip() if column else pd.NA
    rows["company"] = rows["company"].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    rows = rows[rows["company"].notna()].copy()
    for field in NUMERIC_FIELDS:
        column = columns.get(field)
        rows[field] = frame.loc[rows.index, column].map(number) if column else float("nan")
    rows["source_file"] = path.name
    return rows


def _empty_table(path: Path) -> pd.DataFrame:
    columns = ["company", "symbol", "isin", *NUMERIC_FIELDS, "source_file"]
    frame = pd.DataFrame(columns=columns)
    frame["source_file"] = path.name
    return frame


def _score_band(value: float, top: float, middle: float, low: float) -> float:
    if pd.isna(value):
        return float("nan")
    return 100 if value >= top else 75 if value >= middle else 50 if value >= low else 0


def _valuation_score(value: float) -> float:
    if pd.isna(value) or value <= 0:
        return float("nan")
    return 100 if value <= 20 else 75 if value <= 25 else 50 if value <= 35 else 0


def _combine_rows(frame: pd.DataFrame) -> dict:
    names = frame["company"].astype(str).tolist()
    identifiers = {
        field: sorted(set(frame[field].dropna().astype(str).str.strip()))
        for field in ("symbol", "isin")
    }
    key_fields = ["symbol", "isin"]
    record = {
        "company": max(names, key=lambda value: (len(value), value.casefold())),
        "source_asof": "not provided",
        "source_strategies": ";".join(sorted(frame["source_strategy"].unique())),
        "financial_basis_confirmation": "Consolidated (user-confirmed)",
        "count_source_rows": len(frame),
        "source_files": ";".join(sorted(frame["source_file"].unique())),
    }
    conflicts = []
    for field, values in identifiers.items():
        record[field] = values[0] if len(values) == 1 else None
        if len(values) > 1:
            conflicts.append(field)
    for field in NUMERIC_FIELDS:
        values = frame[field].dropna().astype(float).tolist()
        unique_values = {round(value, 6) for value in values}
        record[field] = statistics.median(values) if values else float("nan")
        if len(unique_values) > 1:
            conflicts.append(field)
    record["conflicting_source_values"] = ";".join(conflicts)
    return record


def build_provisional_ranking(
    input_dir: str | Path,
    result_dir: str | Path,
    output_path: str | Path,
) -> pd.DataFrame:
    """Read copied Screener tables and write the above-threshold provisional ranking."""
    input_dir, result_dir, output_path = Path(input_dir), Path(result_dir), Path(output_path)
    source_frames = []
    for strategy, (input_name, result_name) in STRATEGY_SOURCES.items():
        preferred = input_dir / input_name
        fallback = result_dir / result_name
        source = preferred if preferred.is_file() and preferred.stat().st_size else fallback
        frame = _read_table(source)
        frame["source_strategy"] = strategy
        source_frames.append(frame)

    combined = pd.concat(source_frames, ignore_index=True)
    grouped = defaultdict(list)
    for _, row in combined.iterrows():
        identifier = row["isin"]
        symbol = row["symbol"]
        key = (
            f"isin:{str(identifier).strip().upper()}"
            if pd.notna(identifier) and str(identifier).strip()
            else f"symbol:{str(symbol).strip().upper()}"
            if pd.notna(symbol) and str(symbol).strip()
            else f"name:{_company_key(str(row['company']))}"
        )
        grouped[key].append(row)

    candidates = pd.DataFrame([
        _combine_rows(pd.DataFrame(rows))
        for rows in grouped.values()
    ])
    if candidates.empty:
        candidates = pd.DataFrame(columns=[
            "company", "source_asof", "source_strategies",
            "financial_basis_confirmation", "count_source_rows", "source_files",
            "symbol", "isin", *NUMERIC_FIELDS, "conflicting_source_values",
        ])
        for field in NUMERIC_FIELDS:
            candidates[field] = pd.Series(dtype=float)
    candidates["market_cap_over_10000"] = candidates["market_cap"].gt(10000)
    candidates = candidates[candidates["market_cap_over_10000"]].copy()

    for field, cutoffs in (
        ("roce", (20, 15, 12)),
        ("roe", (20, 15, 12)),
        ("quarterly_sales_growth", (15, 10, 5)),
        ("quarterly_profit_growth", (15, 10, 5)),
    ):
        candidates[f"{field}_score"] = candidates[field].map(
            lambda value, thresholds=cutoffs: _score_band(value, *thresholds)
        )
    candidates["business_quality_score"] = candidates[
        ["roce_score", "roe_score"]
    ].mean(axis=1, skipna=True).where(candidates[["roce_score", "roe_score"]].notna().any(axis=1))
    candidates["quarterly_growth_score"] = candidates[
        ["quarterly_sales_growth_score", "quarterly_profit_growth_score"]
    ].mean(axis=1, skipna=True).where(
        candidates[
            ["quarterly_sales_growth_score", "quarterly_profit_growth_score"]
        ].notna().any(axis=1)
    )
    candidates["valuation_score"] = candidates["pe"].map(_valuation_score)
    drawdown = (1 - candidates["market_price"] / candidates["52_week_high"]) * 100
    candidates["drawdown_pct"] = drawdown.where(
        candidates["52_week_high"].gt(0) & candidates["market_price"].notna()
    )
    candidates["price_correction_score"] = score_price_correction(
        candidates["market_price"], candidates["52_week_high"]
    )

    score_fields = list(WEIGHTS)
    available_weights = candidates[score_fields].notna().mul(
        pd.Series(WEIGHTS)
    ).sum(axis=1)
    weighted_points = candidates[score_fields].mul(pd.Series(WEIGHTS)).sum(
        axis=1, min_count=1
    )
    candidates["provisional_score"] = (weighted_points / available_weights).where(
        available_weights.gt(0)
    )
    candidates["provisional_component_coverage_pct"] = available_weights
    candidates["unavailable_components"] = candidates[score_fields].isna().apply(
        lambda row: ";".join(row.index[row].tolist()), axis=1
    )
    candidates = candidates.sort_values(
        [
            "provisional_score", "provisional_component_coverage_pct",
            "business_quality_score", "company",
        ],
        ascending=[False, False, False, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    candidates.insert(0, "rank", range(1, len(candidates) + 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output_path, index=False)
    return candidates

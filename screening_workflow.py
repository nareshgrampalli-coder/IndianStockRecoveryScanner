#!/usr/bin/env python
"""Combine Screener.in CSV exports, add live Yahoo Finance technicals, and rank stocks."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

NIFTY500_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
SCREENER_FILES = ("strategy_1", "strategy_2", "strategy_3", "strategy_4")

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


def normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def normalize_company(value: object) -> str:
    normalized = normalize_header(value)
    normalized = re.sub(r"\b(limited|ltd|private|pvt|company|co)\b", "", normalized)
    return " ".join(normalized.split())


def number(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in ("", "-", "--", "NA", "N/A"):
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def find_column(frame: pd.DataFrame, field: str) -> str | None:
    normalized = {normalize_header(col): col for col in frame.columns}
    aliases = [normalize_header(alias) for alias in ALIASES[field]]
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    for alias in aliases:
        for header, original in normalized.items():
            if alias and alias in header:
                return original
    return None


def read_screener(path: Path, strategy: str) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    symbol_col = find_column(frame, "symbol")
    name_col = find_column(frame, "name")
    if symbol_col is None and name_col is None:
        raise ValueError(f"{path}: expected a Symbol, Ticker, or company Name column")
    rows = pd.DataFrame()
    rows["symbol"] = frame[symbol_col] if symbol_col else ""
    rows["name"] = frame[name_col] if name_col else frame[symbol_col]
    rows["symbol"] = rows["symbol"].astype(str).str.strip().str.upper()
    rows.loc[rows["symbol"].isin(("", "NAN", "NONE")), "symbol"] = ""
    rows["name"] = rows["name"].astype(str).str.strip()
    rows["strategy"] = strategy
    for field in ("roce", "roe", "sales_growth", "profit_growth", "debt_equity",
                  "operating_cash_flow", "pe", "market_cap"):
        col = find_column(frame, field)
        rows[field] = frame[col].map(number) if col else float("nan")
    rows = rows[rows["symbol"].eq("") | rows["symbol"].str.match(r"^[A-Z0-9&.-]+$", na=False)]
    return rows


def load_nifty500() -> pd.DataFrame:
    response = requests.get(
        NIFTY500_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    constituents = pd.read_csv(BytesIO(response.content))
    symbol_col = find_column(constituents, "symbol")
    name_col = find_column(constituents, "name")
    if symbol_col is None:
        raise ValueError("Nifty 500 constituent download did not contain a symbol column")
    result = pd.DataFrame({"symbol": constituents[symbol_col].astype(str).str.upper().str.strip()})
    result["nifty_name"] = constituents[name_col] if name_col else result["symbol"]
    return result.drop_duplicates("symbol")


def mean_present(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    return frame[fields].mean(axis=1, skipna=True)


def score_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    # Each metric is scored 0-100 against explicit, conservative thresholds.
    frame["roce_score"] = frame["roce"].map(lambda x: 100 if x >= 20 else 75 if x >= 15 else 50 if x >= 12 else 0 if pd.notna(x) else float("nan"))
    frame["roe_score"] = frame["roe"].map(lambda x: 100 if x >= 20 else 75 if x >= 15 else 50 if x >= 12 else 0 if pd.notna(x) else float("nan"))
    frame["sales_growth_score"] = frame["sales_growth"].map(lambda x: 100 if x >= 15 else 75 if x >= 10 else 50 if x >= 5 else 0 if pd.notna(x) else float("nan"))
    frame["earnings_growth_score"] = frame["profit_growth"].map(lambda x: 100 if x >= 15 else 75 if x >= 10 else 50 if x >= 5 else 0 if pd.notna(x) else float("nan"))
    frame["debt_score"] = frame["debt_equity"].map(lambda x: 100 if x <= 0.25 else 75 if x <= 0.5 else 50 if x <= 0.7 else 0 if pd.notna(x) else float("nan"))
    frame["cash_flow_score"] = frame["operating_cash_flow"].map(lambda x: 100 if x > 0 else 0 if pd.notna(x) else float("nan"))
    frame["valuation_score"] = frame["pe"].map(lambda x: 100 if 0 < x <= 20 else 75 if 0 < x <= 25 else 50 if 0 < x <= 35 else 0 if pd.notna(x) else float("nan"))
    components = ["roce_score", "roe_score", "sales_growth_score", "earnings_growth_score",
                  "debt_score", "cash_flow_score", "valuation_score"]
    frame["fundamental_score"] = mean_present(frame, components)
    frame["fundamentals_available"] = frame[components].notna().sum(axis=1)
    return frame


def technicals_for(symbol: str) -> dict[str, float]:
    try:
        history = yf.Ticker(f"{symbol}.NS").history(
            period="1y", auto_adjust=True, raise_errors=True, timeout=20
        )
    except Exception as exc:
        return {"technical_error": str(exc)[:240]}
    if history.empty or len(history) < 30:
        return {"technical_error": "Insufficient Yahoo Finance price history"}
    close, volume = history["Close"].dropna(), history["Volume"].dropna()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi_series = 100 - 100 / (1 + rs)
    rsi = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else (100.0 if loss.iloc[-1] == 0 else float("nan"))
    exp12, exp26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    macd, signal = exp12 - exp26, (exp12 - exp26).ewm(span=9, adjust=False).mean()
    price = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else float("nan")
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else float("nan")
    avg_volume = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float("nan")
    volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume and pd.notna(avg_volume) else float("nan")
    support = float(close.tail(20).min())
    return {
        "price_asof": close.index[-1].strftime("%Y-%m-%d"),
        "market_price": price, "rsi14": rsi,
        "macd": float(macd.iloc[-1]), "macd_signal": float(signal.iloc[-1]),
        "macd_bullish": bool(macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]),
        "macd_above_signal": bool(macd.iloc[-1] > signal.iloc[-1]),
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "above_sma20": bool(price > sma20),
        "above_sma50": bool(price > sma50) if pd.notna(sma50) else float("nan"),
        "above_sma200": bool(price > sma200) if pd.notna(sma200) else float("nan"),
        "volume_ratio_20d": volume_ratio, "support_20d": support,
    }


def score_technicals(frame: pd.DataFrame) -> pd.DataFrame:
    frame["rsi_score"] = frame["rsi14"].map(lambda x: 100 if 30 <= x <= 45 else 75 if 45 < x <= 60 else 50 if 25 <= x < 30 else 25 if pd.notna(x) else float("nan"))
    frame["macd_score"] = frame["macd_bullish"].map(lambda x: 100 if x is True or str(x).lower() == "true" else 0 if x is False or str(x).lower() == "false" else float("nan"))
    ma_cols = ["above_sma20", "above_sma50", "above_sma200"]
    frame["moving_average_score"] = frame[ma_cols].apply(
        lambda row: row.map(lambda x: 100 if x is True or str(x).lower() == "true" else 0 if x is False or str(x).lower() == "false" else float("nan")).mean(),
        axis=1,
    )
    frame["volume_score"] = frame["volume_ratio_20d"].map(lambda x: 100 if x >= 1.5 else 75 if x >= 1.0 else 25 if pd.notna(x) else float("nan"))
    frame["support_score"] = frame.apply(
        lambda r: 100 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d")) and r["market_price"] <= r["support_20d"] * 1.05 else
        75 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d")) and r["market_price"] <= r["support_20d"] * 1.10 else
        25 if pd.notna(r.get("market_price")) and pd.notna(r.get("support_20d")) else float("nan"),
        axis=1,
    )
    components = ["rsi_score", "macd_score", "moving_average_score", "volume_score", "support_score"]
    frame["technical_score"] = mean_present(frame, components)
    frame["technical_available"] = frame[components].notna().sum(axis=1)
    return frame


def run(args: argparse.Namespace) -> Path:
    files = [Path(getattr(args, name)) for name in SCREENER_FILES]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing screener export(s): " + ", ".join(missing))
    imports = pd.concat([read_screener(path, name) for name, path in zip(SCREENER_FILES, files)], ignore_index=True)
    universe = load_nifty500()
    universe_symbols = set(universe["symbol"])
    name_to_symbol = {
        normalize_company(name): symbol
        for name, symbol in zip(universe["nifty_name"], universe["symbol"])
    }
    imports["symbol"] = imports.apply(
        lambda row: row["symbol"] if row["symbol"] in universe_symbols
        else name_to_symbol.get(normalize_company(row["name"]), ""),
        axis=1,
    )
    imports = imports[imports["symbol"].ne("")]
    if imports.empty:
        raise ValueError("No Screener rows matched Nifty 500 symbols or constituent company names.")
    # Retain the newest non-empty value per field when the same company appears in multiple screens.
    imports = imports.sort_values("strategy").groupby("symbol", as_index=False).agg(
        {**{field: "first" for field in ("name", "roce", "roe", "sales_growth", "profit_growth",
                                         "debt_equity", "operating_cash_flow", "pe", "market_cap")},
         "strategy": lambda values: ", ".join(sorted(set(values)))}
    )
    candidates = imports.merge(universe, on="symbol", how="inner")
    if candidates.empty:
        raise ValueError("No matching Nifty 500 stocks found. Check the screener exports' symbol format.")
    candidates = score_fundamentals(candidates)
    technical_results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(technicals_for, symbol): index
            for index, symbol in candidates["symbol"].items()
        }
        for future in as_completed(futures):
            technical_results[futures[future]] = future.result()
    tech = pd.DataFrame.from_dict(technical_results, orient="index").reindex(candidates.index)
    candidates = score_technicals(pd.concat([candidates, tech], axis=1))
    strategies = candidates["strategy"].fillna("").str.split(", ")
    candidates["strategy_3_primary"] = strategies.map(lambda values: "strategy_3" in values)
    candidates["strategy_1_quality"] = strategies.map(lambda values: "strategy_1" in values)
    candidates["strategy_4_entry_timing"] = strategies.map(lambda values: "strategy_4" in values)
    candidates["strategy_2_deep_value"] = strategies.map(lambda values: "strategy_2" in values)
    candidates["combined_score"] = candidates[["fundamental_score", "technical_score"]].mean(axis=1)
    candidates = candidates.sort_values(
        ["combined_score", "strategy_3_primary", "strategy_1_quality",
         "strategy_4_entry_timing", "fundamental_score"],
        ascending=False,
        na_position="last",
    )
    candidates.insert(0, "rank", range(1, len(candidates) + 1))
    candidates["research_shortlist"] = candidates["rank"] <= 15
    candidates["screened_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        candidates.to_excel(writer, sheet_name="Ranked Watchlist", index=False)
        candidates[candidates["research_shortlist"]].to_excel(writer, sheet_name="Top 15 Research", index=False)
        imports.to_excel(writer, sheet_name="Combined Screen Imports", index=False)
        universe.to_excel(writer, sheet_name="Nifty 500 Universe", index=False)
        notes = pd.DataFrame([
            ["Fundamental data", "Imported from the provided Screener.in CSV exports; most recent available non-empty value is retained."],
            ["Technical data", "Yahoo Finance daily adjusted price/volume history. Prices can differ from Screener.in export date."],
            ["Universe", f"Downloaded from Nifty Indices: {NIFTY500_URL}"],
            ["Scoring", "Each available metric is scored 0-100; group scores average available components only."],
            ["Overall score", "Equal-weight average of fundamental and technical group scores; missing groups are excluded."],
            ["Strategy priority", "Strategy 3 is the primary screen; Strategy 1 is the quality-filter flag; Strategy 4 is the entry-timing flag. These flags are shown in the ranked sheet and break ties after combined score."],
            ["ROCE / ROE points", ">=20: 100; >=15: 75; >=12: 50; lower: 0."],
            ["Growth points", ">=15%: 100; >=10%: 75; >=5%: 50; lower: 0."],
            ["Debt points", "<=0.25: 100; <=0.50: 75; <=0.70: 50; higher: 0."],
            ["Cash flow points", "Positive operating cash flow: 100; zero/negative: 0."],
            ["P/E points", "Positive P/E <=20: 100; <=25: 75; <=35: 50; higher/non-positive: 0."],
            ["RSI points", "30-45: 100 (oversold reversal zone); >45-60: 75; 25-<30: 50; other valid readings: 25."],
            ["MACD points", "100 for a fresh bullish MACD/signal crossover on the latest daily candle; otherwise 0 when data is available."],
            ["Technical support", "20-day closing low proxy; price within 5%: 100, within 10%: 75, otherwise 25."],
            ["Caveat", "A screen/score is not investment advice. Verify company filings, data timestamps, liquidity, corporate actions and risks before investing."],
        ], columns=["Item", "Definition"])
        notes.to_excel(writer, sheet_name="Scoring & Sources", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for col in sheet.columns:
                letter = col[0].column_letter
                width = min(max(max(len(str(cell.value or "")) for cell in col) + 2, 12), 42)
                sheet.column_dimensions[letter].width = width
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for strategy in SCREENER_FILES:
        parser.add_argument(f"--{strategy.replace('_', '-')}", dest=strategy, required=True, help=f"CSV export for {strategy.replace('_', ' ')}")
    parser.add_argument("--output", default="screening_results.xlsx", help="Output workbook path")
    args = parser.parse_args()
    try:
        output = run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Workbook written: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

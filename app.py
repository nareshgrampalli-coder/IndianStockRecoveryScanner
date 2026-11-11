#!/usr/bin/env python
"""Combine four Screener exports, enrich with price data, score, and rank."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

from data_processing.financial_cleaner import normalize_company
from data_sources.nse_provider import NSEProvider
from data_sources.screener_importer import read_screener
from data_sources.yahoo_provider import YahooProvider
from indicators.macd import macd
from indicators.moving_averages import moving_averages
from indicators.rsi import rsi
from scoring.final_ranker import rank_candidates
from scoring.fundamental_score import score_fundamentals
from scoring.technical_score import score_technicals

STRATEGIES = ("strategy_1", "strategy_2", "strategy_3", "strategy_4")
DEFAULTS = {
    "universe_url": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "request_timeout_seconds": 30,
    "technical_workers": 5,
    "history_period": "1y",
}


def load_settings(path: Path) -> dict:
    settings = DEFAULTS.copy()
    if not path.exists():
        return settings
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip().strip("\"'") for part in line.split(":", 1))
        if key in settings:
            default = settings[key]
            settings[key] = type(default)(value)
    return settings


def technicals_for(symbol: str, provider: YahooProvider) -> dict:
    try:
        history = provider.history(symbol)
    except Exception as exc:
        return {"technical_error": str(exc)[:240]}
    if history.empty or len(history) < 30:
        return {"technical_error": "Insufficient Yahoo Finance price history"}
    close, volume = history["Close"].dropna(), history["Volume"].dropna()
    rsi_series = rsi(close)
    macd_line, signal_line = macd(close)
    averages = moving_averages(close)
    average_volume = volume.rolling(20).mean()
    latest_volume_avg = average_volume.iloc[-1] if len(average_volume) else float("nan")
    latest_rsi = rsi_series.iloc[-1]
    return {
        "price_asof": close.index[-1].strftime("%Y-%m-%d"),
        "market_price": float(close.iloc[-1]),
        "rsi14": float(latest_rsi) if pd.notna(latest_rsi) else float("nan"),
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "macd_bullish": bool(macd_line.iloc[-1] > signal_line.iloc[-1]
                             and macd_line.iloc[-2] <= signal_line.iloc[-2]),
        "macd_above_signal": bool(macd_line.iloc[-1] > signal_line.iloc[-1]),
        "sma20": float(averages[20].iloc[-1]),
        "sma50": float(averages[50].iloc[-1]) if len(close) >= 50 else float("nan"),
        "sma200": float(averages[200].iloc[-1]) if len(close) >= 200 else float("nan"),
        "above_sma20": bool(close.iloc[-1] > averages[20].iloc[-1]),
        "above_sma50": bool(close.iloc[-1] > averages[50].iloc[-1]) if len(close) >= 50 else float("nan"),
        "above_sma200": bool(close.iloc[-1] > averages[200].iloc[-1]) if len(close) >= 200 else float("nan"),
        "volume_ratio_20d": float(volume.iloc[-1] / latest_volume_avg)
        if pd.notna(latest_volume_avg) and latest_volume_avg != 0 else float("nan"),
        "support_20d": float(close.tail(20).min()),
    }


def run(args: argparse.Namespace) -> Path:
    settings = load_settings(Path(args.settings))
    inputs = [Path(getattr(args, name)) for name in STRATEGIES]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing screener export(s): " + ", ".join(missing))

    imports = pd.concat(
        [read_screener(path, name) for name, path in zip(STRATEGIES, inputs)],
        ignore_index=True,
    )
    universe = NSEProvider(
        settings["universe_url"], settings["request_timeout_seconds"]
    ).nifty500()
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
    aggregate = {
        field: "first" for field in (
            "name", "roce", "roe", "sales_growth", "profit_growth", "debt_equity",
            "operating_cash_flow", "pe", "market_cap",
        )
    }
    imports = imports.sort_values("strategy").groupby("symbol", as_index=False).agg(
        {**aggregate, "strategy": lambda values: ", ".join(sorted(set(values)))}
    )
    candidates = imports.merge(universe, on="symbol", how="inner")
    if candidates.empty:
        raise ValueError("No matching Nifty 500 stocks found. Check the screener exports' symbol format.")

    candidates = score_fundamentals(candidates)
    provider = YahooProvider(settings["history_period"])
    results = {}
    with ThreadPoolExecutor(max_workers=settings["technical_workers"]) as executor:
        futures = {
            executor.submit(technicals_for, symbol, provider): index
            for index, symbol in candidates["symbol"].items()
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    technical_data = pd.DataFrame.from_dict(results, orient="index").reindex(candidates.index)
    candidates = score_technicals(pd.concat([candidates, technical_data], axis=1))
    candidates = rank_candidates(candidates)
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
            ["Technical data", "Yahoo Finance daily adjusted price/volume history; values may have a different as-of date."],
            ["Universe", f"Downloaded from NSE Indices: {settings['universe_url']}"],
            ["Scoring", "Each available metric is scored 0-100; group scores average available components only."],
            ["Overall score", "Equal-weight average of fundamental and technical group scores; missing groups are excluded."],
            ["Strategy priority", "Strategy 3 is the primary screen; Strategy 1 is the quality-filter flag; Strategy 4 is the entry-timing flag. These flags break ties after combined score."],
            ["ROCE / ROE points", ">=20: 100; >=15: 75; >=12: 50; lower: 0."],
            ["Growth points", ">=15%: 100; >=10%: 75; >=5%: 50; lower: 0."],
            ["Debt points", "<=0.25: 100; <=0.50: 75; <=0.70: 50; higher: 0."],
            ["Cash flow points", "Positive operating cash flow: 100; zero/negative: 0."],
            ["P/E points", "Positive P/E <=20: 100; <=25: 75; <=35: 50; higher/non-positive: 0."],
            ["RSI points", "30-45: 100; >45-60: 75; 25-<30: 50; other valid readings: 25."],
            ["MACD points", "100 for a fresh bullish MACD/signal crossover on the latest daily candle; otherwise 0 when data is available."],
            ["Technical support", "20-day closing low proxy; price within 5%: 100, within 10%: 75, otherwise 25."],
            ["Caveat", "A screen/score is not investment advice. Verify company filings, timestamps, liquidity, corporate actions and risks."],
        ], columns=["Item", "Definition"])
        notes.to_excel(writer, sheet_name="Scoring & Sources", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                letter = column[0].column_letter
                width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 42)
                sheet.column_dimensions[letter].width = width
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for strategy in STRATEGIES:
        parser.add_argument(f"--{strategy.replace('_', '-')}", dest=strategy, required=True)
    parser.add_argument("--output", default="screening_results.xlsx")
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args(argv)
    try:
        output = run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Workbook written: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Combine four Screener exports, enrich with price data, score, and rank."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

from config.runtime import load_settings
from data_processing.corporate_actions import apply_adjustments
from data_processing.data_validator import validate_prices
from data_processing.financial_cleaner import normalize_company
from data_processing.price_cleaner import clean_prices
from data_processing.security_master import apply_security_mappings, load_security_mappings
from database.models import FundamentalObservation, PriceBar, SecurityMapping
from database.repository import ScreeningRepository
from data_sources.nse_provider import NSEProvider
from data_sources.screener_importer import read_screener
from data_sources.yahoo_provider import YahooProvider
from indicators.macd import macd
from indicators.moving_averages import moving_averages
from indicators.rsi import rsi
from scoring.final_ranker import rank_candidates
from scoring.fundamental_score import score_fundamentals
from scoring.technical_score import score_technicals
from strategies.screen_results import write_strategy_results

STRATEGIES = ("strategy_1", "strategy_2", "strategy_3", "strategy_4")
def technicals_for(symbol: str, provider: YahooProvider) -> tuple[dict, list[dict]]:
    try:
        history = clean_prices(provider.history(symbol))
        prices = apply_adjustments(history)
        validate_prices(prices)
    except Exception as exc:
        return {"technical_error": str(exc)[:240]}, []
    close, volume = prices["close"].dropna(), prices["volume"].dropna()
    if prices.empty or len(close) < 30:
        return {"technical_error": "Insufficient Yahoo Finance price history"}, []
    rsi_series = rsi(close)
    macd_line, signal_line = macd(close)
    averages = moving_averages(close)
    average_volume = volume.rolling(20).mean()
    latest_volume_avg = average_volume.iloc[-1] if len(average_volume) else float("nan")
    latest_rsi = rsi_series.iloc[-1]
    retrieved_at = datetime.now(timezone.utc).isoformat()
    raw_columns = ["raw_open", "raw_high", "raw_low", "raw_close"]
    adjusted_columns = ["adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close"]
    quality_columns = raw_columns + adjusted_columns + ["volume", "adjustment_factor"]
    bars = [
        {
            "session_date": index.strftime("%Y-%m-%d"),
            **{column: float(row[column]) for column in raw_columns + adjusted_columns
               if pd.notna(row[column])},
            "volume": float(row["volume"]) if pd.notna(row["volume"]) else None,
            "adjustment_factor": float(row["adjustment_factor"]),
            "data_quality_score": float(row[quality_columns].notna().mean() * 100),
            "retrieved_at_utc": retrieved_at,
        }
        for index, row in prices.iterrows()
    ]
    metrics = {
        "price_asof": close.index[-1].strftime("%Y-%m-%d"),
        "market_price": float(close.iloc[-1]),
        "price_high_1y": float(close.max()),
        "data_provider": "Yahoo Finance",
        "price_retrieved_at_utc": retrieved_at,
        "price_data_quality_score": bars[-1]["data_quality_score"],
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
    return metrics, bars


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
    mappings = load_security_mappings(settings["security_master_path"])
    universe = apply_security_mappings(universe, mappings)
    universe_symbols = set(universe["symbol"])
    isin_to_symbol = dict(zip(universe["isin"], universe["symbol"]))
    name_to_symbol = {
        normalize_company(name): symbol
        for name, symbol in zip(universe["nifty_name"], universe["symbol"])
    }
    imports["symbol"] = imports.apply(
        lambda row: isin_to_symbol.get(row["isin"], "")
        if pd.notna(row.get("isin"))
        else row["symbol"] if row["symbol"] in universe_symbols
        else name_to_symbol.get(normalize_company(row["name"]), ""),
        axis=1,
    )
    imports = imports[imports["symbol"].ne("")]
    if imports.empty:
        raise ValueError("No Screener rows matched Nifty 500 symbols or constituent company names.")
    aggregate = {
        field: "first" for field in (
            "name", "roce", "roe", "sales_growth", "profit_growth", "debt_equity",
            "operating_cash_flow", "pe", "market_cap", "promoter_holding", "promoter_pledging",
            "financial_basis", "financial_period", "publication_date", "data_provider",
            "retrieved_at_utc", "data_quality_score", "financial_data_missing_fields",
        )
    }
    imports["_publication_sort"] = pd.to_datetime(
        imports["publication_date"], errors="coerce", utc=True
    )
    imports["_period_sort"] = pd.to_datetime(
        imports["financial_period"], errors="coerce", utc=True
    )
    imports = imports.sort_values(
        ["_publication_sort", "_period_sort"], ascending=False, na_position="last"
    ).groupby("symbol", as_index=False).agg(
        {**aggregate, "strategy": lambda values: ", ".join(sorted(set(values)))}
    )
    candidates = imports.merge(universe, on="symbol", how="inner")
    if candidates.empty:
        raise ValueError("No matching Nifty 500 stocks found. Check the screener exports' symbol format.")

    candidates = score_fundamentals(candidates)
    provider = YahooProvider(settings["history_period"])
    results, price_bars = {}, {}
    with ThreadPoolExecutor(max_workers=settings["technical_workers"]) as executor:
        futures = {
            executor.submit(technicals_for, symbol, provider): index
            for index, symbol in candidates["symbol"].items()
        }
        for future in as_completed(futures):
            index = futures[future]
            metrics, bars = future.result()
            results[index] = metrics
            price_bars[index] = bars
    technical_data = pd.DataFrame.from_dict(results, orient="index").reindex(candidates.index)
    candidates = score_technicals(pd.concat([candidates, technical_data], axis=1))
    candidates = rank_candidates(candidates)
    candidates["screened_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    write_strategy_results(candidates, args.strategy_results_dir)

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
            ["Strategy-specific weights", "Each strategy uses its own 100-point component weight profile; see the project architecture documentation."],
            ["Overall score", "Candidates in multiple strategies are scored with each applicable profile and the scores are averaged; missing components are renormalized within each profile. score_coverage_pct reports average original weight coverage."],
            ["Financial quality", "Mean of ROCE, ROE and operating-cash-flow scores; missing metrics are excluded."],
            ["Earnings growth", "Mean of sales-growth and profit-growth scores; missing metrics are excluded."],
            ["Price correction", "Drawdown from the highest Yahoo adjusted close in available one-year history is scored in bands and multiplied by mean financial-quality and earnings-growth evidence; without either evidence source the component is unscored."],
            ["Technical reversal", "Strategy 4 technical score weights momentum 50% (RSI 40%, MACD 35%, moving averages 25%), volume 30%, and support 20%."],
            ["Risk and governance", "Mean of available debt/equity, promoter-holding and promoter-pledging scores; unavailable fields are excluded."],
            ["Strategy priority", "Strategy 3 is the primary screen; Strategy 1 is the quality-filter flag; Strategy 4 is the entry-timing flag. These flags break ties after combined score."],
            ["ROCE / ROE points", ">=20: 100; >=15: 75; >=12: 50; lower: 0."],
            ["Growth points", ">=15%: 100; >=10%: 75; >=5%: 50; lower: 0."],
            ["Debt points", "<=0.25: 100; <=0.50: 75; <=0.70: 50; higher: 0."],
            ["Cash flow points", "Positive operating cash flow: 100; zero/negative: 0."],
            ["P/E points", "Positive P/E <=20: 100; <=25: 75; <=35: 50; higher/non-positive: 0."],
            ["RSI points", "30-45: 100; >45-60: 75; 25-<30: 50; other valid readings: 25."],
            ["MACD points", "100 for a fresh bullish MACD/signal crossover on the latest daily candle; otherwise 0 when data is available."],
            ["Technical support", "20-day closing low proxy; price within 5%: 100, within 10%: 75, otherwise 25."],
            ["Canonical identifier", "ISIN identifies each company; NSE and BSE symbols are retained as mappings."],
            ["Price storage", "Raw and adjusted OHLC are stored separately. Adjusted OHLC uses provider adjusted-close factors before indicator/drawdown calculation."],
            ["Financial statement basis", "Only input rows explicitly labeled consolidated are accepted."],
            ["Financial provenance", "Financial period, publication date, provider, retrieval timestamp and a completeness-based quality score are retained; missing metrics remain unavailable."],
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

    retrieved_at = datetime.now(timezone.utc).isoformat()
    security_records = [
        SecurityMapping(
                isin=row.isin,
                company_name=str(row.nifty_name),
                nse_symbol=str(row.nse_symbol) if pd.notna(row.nse_symbol) else None,
                bse_symbol=str(row.bse_symbol) if pd.notna(row.bse_symbol) else None,
        )
        for row in universe.itertuples(index=False)
    ]
    stored_prices = []
    for index, bars in price_bars.items():
        isin = candidates.loc[index, "isin"]
        if pd.isna(isin):
            continue
        stored_prices.extend(
            PriceBar(isin=str(isin), provider="Yahoo Finance", **bar)
            for bar in bars
        )
    fundamental_records = []
    for row in candidates.itertuples(index=False):
        payload_fields = (
            "roce", "roe", "sales_growth", "profit_growth", "debt_equity",
            "operating_cash_flow", "pe", "market_cap", "promoter_holding",
            "promoter_pledging", "financial_data_missing_fields",
        )
        payload = {
            field: (None if pd.isna(getattr(row, field)) else getattr(row, field))
            for field in payload_fields
        }
        fundamental_records.append(FundamentalObservation(
            isin=str(row.isin),
            financial_period=None if pd.isna(row.financial_period) else str(row.financial_period),
            publication_date=None if pd.isna(row.publication_date) else str(row.publication_date),
            financial_basis=str(row.financial_basis),
            data_provider=str(row.data_provider),
            retrieved_at_utc=(
                str(row.retrieved_at_utc)
                if pd.notna(row.retrieved_at_utc) else retrieved_at
            ),
            data_quality_score=float(row.data_quality_score),
            payload=json.dumps(payload, default=str),
        ))
    ScreeningRepository(settings["database_path"]).save_market_data(
        security_records, stored_prices, fundamental_records
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for strategy in STRATEGIES:
        parser.add_argument(f"--{strategy.replace('_', '-')}", dest=strategy, required=True)
    parser.add_argument("--output", default="screening_results.xlsx")
    parser.add_argument("--strategy-results-dir", default="strategy_results")
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args(argv)
    try:
        output = run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Workbook written: {output.resolve()}")
    print(f"Strategy result CSVs written to: {Path(args.strategy_results_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

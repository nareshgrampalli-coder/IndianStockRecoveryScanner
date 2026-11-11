#!/usr/bin/env python
"""Run one implemented strategy against a consolidated Screener CSV."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd

from app import technicals_for
from config.runtime import load_settings
from data_processing.financial_cleaner import normalize_company
from data_sources.nse_provider import NSEProvider
from data_sources.screener_importer import read_screener
from data_sources.yahoo_provider import YahooProvider
from strategies.screen_results import MATCHERS, matching_rows


def run(strategy: str, input_path: str | Path, output_path: str | Path,
        settings_path: str | Path) -> Path:
    settings = load_settings(settings_path)
    source = Path(input_path)
    output = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Screener export not found: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("Output CSV must not overwrite the Screener input")

    candidates = read_screener(source, strategy)
    universe = NSEProvider(
        settings["universe_url"], settings["request_timeout_seconds"]
    ).nifty500()
    isin_to_symbol = dict(zip(universe["isin"], universe["symbol"]))
    symbols = set(universe["symbol"])
    name_to_symbol = {
        normalize_company(name): symbol
        for name, symbol in zip(universe["nifty_name"], universe["symbol"])
    }

    def resolve(row):
        if pd.notna(row["isin"]):
            return isin_to_symbol.get(row["isin"], "")
        if row["symbol"] in symbols:
            return row["symbol"]
        return name_to_symbol.get(normalize_company(row["name"]), "")

    candidates["symbol"] = candidates.apply(resolve, axis=1)
    candidates = candidates[candidates["symbol"].ne("")].copy()
    if candidates.empty:
        raise ValueError("No Screener rows matched Nifty 500 symbols or company names")
    symbol_to_isin = dict(zip(universe["symbol"], universe["isin"]))
    candidates["isin"] = candidates["symbol"].map(symbol_to_isin)

    provider = YahooProvider(settings["history_period"])
    with ThreadPoolExecutor(max_workers=settings["technical_workers"]) as executor:
        technical_rows = list(executor.map(
            lambda symbol: technicals_for(symbol, provider),
            candidates["symbol"],
        ))
    metrics = pd.DataFrame([row[0] for row in technical_rows], index=candidates.index)
    candidates = pd.concat([candidates, metrics], axis=1)

    results = matching_rows(candidates, strategy)
    results["strategy_rule"] = strategy
    results["screened_at_utc"] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", choices=tuple(MATCHERS), required=True)
    parser.add_argument("--input", required=True, help="Consolidated Screener CSV")
    parser.add_argument("--output", required=True, help="Path for matching-result CSV")
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args(argv)
    try:
        output = run(args.strategy, args.input, args.output, args.settings)
    except Exception as exc:
        print(f"Strategy screening failed: {exc}", file=sys.stderr)
        return 1
    print(f"Strategy results written: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

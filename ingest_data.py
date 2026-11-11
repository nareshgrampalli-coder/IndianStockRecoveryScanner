#!/usr/bin/env python
"""Ingest Nifty 500 constituents, four consolidated screens, and daily history."""

import argparse
import sys

from config.runtime import load_settings
from data_processing.ingestion import STRATEGIES, run_ingestion
from data_sources.nse_provider import NSEProvider
from data_sources.yahoo_provider import YahooProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for strategy in STRATEGIES:
        parser.add_argument(
            f"--{strategy.replace('_', '-')}",
            dest=strategy,
            required=True,
            help=f"Consolidated Screener CSV for {strategy.replace('_', ' ')}",
        )
    parser.add_argument("--output-dir", default="normalized_data")
    parser.add_argument("--bhavcopy-csv", help="Optional same-session NSE Bhavcopy CSV for close validation")
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args(argv)
    settings = load_settings(args.settings)
    strategies = {name: getattr(args, name) for name in STRATEGIES}
    try:
        paths = run_ingestion(
            universe_provider=NSEProvider(
                settings["universe_url"], settings["request_timeout_seconds"]
            ),
            price_provider=YahooProvider(settings["ingestion_history_period"]),
            strategy_paths=strategies,
            settings=settings,
            output_dir=args.output_dir,
            bhavcopy_path=args.bhavcopy_csv,
        )
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    for dataset, path in paths.items():
        print(f"{dataset}: {path.resolve()}")
    print(f"Historical provider: Yahoo Finance ({settings['ingestion_history_period']})")
    if not args.bhavcopy_csv:
        print("Price validation: NSE Bhavcopy not supplied; validation status is NOT_PROVIDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

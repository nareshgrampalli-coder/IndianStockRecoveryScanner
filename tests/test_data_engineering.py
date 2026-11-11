from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from backtesting.strategy_backtester import (
    backtest_with_fundamentals,
    point_in_time_fundamentals,
)
from data_processing.corporate_actions import apply_adjustments
from data_sources.screener_importer import read_screener
from database.models import FundamentalObservation, PriceBar, SecurityMapping
from database.repository import ScreeningRepository


class DataEngineeringTests(unittest.TestCase):
    def test_adjusted_ohlc_retains_raw_values(self):
        raw = pd.DataFrame({
            "Open": [100.0],
            "High": [110.0],
            "Low": [90.0],
            "Close": [100.0],
            "Adj Close": [50.0],
            "Volume": [1000],
        }, index=pd.to_datetime(["2024-01-01"]))
        adjusted = apply_adjustments(raw)
        self.assertEqual(adjusted.iloc[0]["raw_close"], 100)
        self.assertEqual(adjusted.iloc[0]["adjusted_close"], 50)
        self.assertEqual(adjusted.iloc[0]["adjusted_open"], 50)
        self.assertEqual(adjusted.iloc[0]["volume"], 1000)

    def test_screener_import_requires_consolidated_basis_and_tracks_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "screen.csv"
            pd.DataFrame([{
                "Symbol": "ABC",
                "Statement Type": "Consolidated",
                "Financial Period": "2023-12-31",
                "Publication Date": "2024-02-01",
                "ROCE": 20,
                "ISIN": "INE000A01000",
            }]).to_csv(path, index=False)
            row = read_screener(path, "strategy_1").iloc[0]
            self.assertEqual(row["financial_basis"], "consolidated")
            self.assertEqual(row["financial_period"], "2023-12-31")
            self.assertEqual(row["publication_date"], "2024-02-01")
            self.assertEqual(row["data_provider"], "Screener.in")
            self.assertTrue(row["retrieved_at_utc"])
            self.assertLess(row["data_quality_score"], 100)
            self.assertIn("roe", row["financial_data_missing_fields"])

            pd.DataFrame([{"Symbol": "ABC", "ROCE": 20}]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "missing financial statement basis"):
                read_screener(path, "strategy_1")

            pd.DataFrame([{
                "Symbol": "ABC", "Statement Type": "Standalone", "ROCE": 20,
            }]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "only consolidated"):
                read_screener(path, "strategy_1")

    def test_point_in_time_backtest_excludes_future_and_unknown_observations(self):
        fundamentals = pd.DataFrame([
            {
                "isin": "INE000A01000", "financial_basis": "consolidated",
                "financial_period": "2023-12-31", "publication_date": "2024-01-02",
            },
            {
                "isin": "INE000B01000", "financial_basis": "consolidated",
                "financial_period": "2024-03-31", "publication_date": "2024-04-15",
            },
            {
                "isin": "INE000D01000", "financial_basis": "consolidated",
                "financial_period": "2024-03-31", "publication_date": "2024-01-02",
            },
            {
                "isin": "INE000E01000", "financial_basis": "consolidated",
                "financial_period": "2023-12-31", "publication_date": "2024-01-03",
            },
            {
                "isin": "INE000C01000", "financial_basis": "consolidated",
                "financial_period": "2023-12-31", "publication_date": None,
            },
        ])
        as_of = point_in_time_fundamentals(fundamentals, "2024-01-03")
        self.assertEqual(as_of["isin"].tolist(), ["INE000A01000"])

        dates = pd.date_range("2024-01-01", periods=4)
        close = pd.Series([10, 11, 12, 13], index=dates)
        calls = []

        def builder(price_history, visible_financials):
            calls.append((len(price_history), set(visible_financials["isin"])))
            return not visible_financials.empty

        result = backtest_with_fundamentals(close, fundamentals, builder)
        self.assertEqual(calls[0], (1, set()))
        self.assertEqual(calls[2], (3, {"INE000A01000"}))
        self.assertEqual(result.loc[dates[3], "strategy_return"], close.pct_change().iloc[3])

    def test_repository_persists_identifiers_raw_adjusted_prices_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "screening.sqlite3"
            repository = ScreeningRepository(path)
            repository.save_market_data(
                [SecurityMapping("INE000A01000", "ABC Ltd", "ABC", "500001")],
                [PriceBar(
                    isin="INE000A01000", session_date="2024-01-01",
                    provider="Yahoo Finance", retrieved_at_utc="2024-01-02T00:00:00+00:00",
                    data_quality_score=100, raw_open=100, raw_high=110, raw_low=90,
                    raw_close=100, adjusted_open=50, adjusted_high=55,
                    adjusted_low=45, adjusted_close=50, volume=1000,
                    adjustment_factor=0.5,
                )],
                [FundamentalObservation(
                    isin="INE000A01000", financial_period="2023-12-31",
                    publication_date="2024-02-01", financial_basis="consolidated",
                    data_provider="Screener.in",
                    retrieved_at_utc="2024-02-02T00:00:00+00:00",
                    data_quality_score=80, payload='{"roce":20}',
                )],
            )
            with closing(sqlite3.connect(path)) as connection:
                mapping = connection.execute(
                    "SELECT isin, nse_symbol, bse_symbol FROM security_master"
                ).fetchone()
                price = connection.execute(
                    "SELECT raw_close, adjusted_close, data_quality_score FROM price_bars"
                ).fetchone()
                financial = connection.execute(
                    "SELECT financial_period, publication_date, financial_basis, data_provider "
                    "FROM fundamental_observations"
                ).fetchone()
            self.assertEqual(mapping, ("INE000A01000", "ABC", "500001"))
            self.assertEqual(price, (100, 50, 100))
            self.assertEqual(
                financial,
                ("2023-12-31", "2024-02-01", "consolidated", "Screener.in"),
            )


if __name__ == "__main__":
    unittest.main()

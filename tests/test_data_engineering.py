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
from data_processing.ingestion import (
    combine_strategy_exports,
    load_nse_bhavcopy,
    normalize_price_history,
    run_ingestion,
    validate_latest_prices,
)
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
                "Sales Growth 3Years": 25,
                "Profit Growth 3Years": 26,
                "Quarterly Sales Growth": 12,
                "Quarterly Profit Growth": 14,
                "ISIN": "INE000A01000",
            }]).to_csv(path, index=False)
            row = read_screener(path, "strategy_1").iloc[0]
            self.assertEqual(row["financial_basis"], "consolidated")
            self.assertEqual(row["financial_period"], "2023-12-31")
            self.assertEqual(row["publication_date"], "2024-02-01")
            self.assertEqual(row["data_provider"], "Screener.in")
            self.assertEqual(row["quarterly_sales_growth"], 12)
            self.assertEqual(row["quarterly_profit_growth"], 14)
            self.assertEqual(row["sales_growth"], 25)
            self.assertEqual(row["profit_growth"], 26)
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

    def test_ingestion_normalizes_all_strategy_memberships_and_missing_values(self):
        universe = pd.DataFrame([
            {
                "isin": "INE000A01000", "symbol": "ABC", "nse_symbol": "ABC",
                "bse_symbol": pd.NA, "nifty_name": "ABC Ltd",
            },
            {
                "isin": "INE000B01000", "symbol": "XYZ", "nse_symbol": "XYZ",
                "bse_symbol": pd.NA, "nifty_name": "XYZ Ltd",
            },
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = {}
            for index, strategy in enumerate(
                ("strategy_1", "strategy_2", "strategy_3", "strategy_4"), 1
            ):
                path = Path(temp_dir) / f"{strategy}.csv"
                pd.DataFrame([{
                    "Symbol": "ABC", "ISIN": "INE000A01000",
                    "Statement Type": "Consolidated",
                    "Financial Period": "2023-12-31",
                    "Publication Date": "2024-02-01",
                    "ROCE": 20,
                }]).to_csv(path, index=False)
                paths[strategy] = path
            stocks = combine_strategy_exports(universe, paths).set_index("isin")
        self.assertEqual(len(stocks), 2)
        self.assertTrue(all(
            stocks.loc["INE000A01000", f"{strategy}_member"]
            for strategy in ("strategy_1", "strategy_2", "strategy_3", "strategy_4")
        ))
        self.assertEqual(stocks.loc["INE000A01000", "roce"], 20)
        self.assertTrue(pd.isna(stocks.loc["INE000A01000", "roe"]))
        self.assertEqual(stocks.loc["INE000B01000", "financial_data_quality_score"], 0)
        self.assertIn("roce", stocks.loc["INE000B01000", "financial_data_missing_fields"])

    def test_ingestion_prices_and_same_session_bhavcopy_validation(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03"])
        history = pd.DataFrame({
            "Open": [100, 101], "High": [102, 103], "Low": [99, 100],
            "Close": [101, 102], "Adj Close": [50.5, 51], "Volume": [1000, 1100],
        }, index=index)
        prices, bars = normalize_price_history(
            "INE000A01000", "ABC", history, "test provider",
            "2024-01-04T00:00:00+00:00",
        )
        self.assertEqual(len(bars), 2)
        self.assertEqual(prices.iloc[-1]["raw_close"], 102)
        self.assertEqual(prices.iloc[-1]["adjusted_close"], 51)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bhavcopy.csv"
            pd.DataFrame([{
                "ISIN": "INE000A01000", "TradDt": "2024-01-03", "ClsPric": 102,
            }]).to_csv(path, index=False)
            bhavcopy = load_nse_bhavcopy(path)
        stocks = pd.DataFrame([{"isin": "INE000A01000"}])
        validated = validate_latest_prices(stocks, prices.reset_index(drop=True), bhavcopy)
        self.assertEqual(validated.loc[0, "price_validation_status"], "MATCH")
        self.assertEqual(validated.loc[0, "price_validation_diff_pct"], 0)

    def test_ingestion_run_emits_full_universe_and_persists_history(self):
        class FakeUniverse:
            def nifty500(self):
                return pd.DataFrame([
                    {
                        "isin": "INE000A01000", "symbol": "ABC",
                        "nse_symbol": "ABC", "bse_symbol": pd.NA,
                        "nifty_name": "ABC Ltd",
                    },
                    {
                        "isin": "INE000B01000", "symbol": "XYZ",
                        "nse_symbol": "XYZ", "bse_symbol": pd.NA,
                        "nifty_name": "XYZ Ltd",
                    },
                ])

        class FakePrices:
            name = "Test EOD provider"

            def history(self, symbol):
                index = pd.date_range("2024-01-02", periods=3)
                close = [100.0, 101.0, 102.0] if symbol == "ABC" else [50.0, 51.0, 52.0]
                return pd.DataFrame({
                    "Open": close,
                    "High": [value + 1 for value in close],
                    "Low": [value - 1 for value in close],
                    "Close": close,
                    "Adj Close": [value * 0.9 for value in close],
                    "Volume": [1000, 1100, 1200],
                }, index=index)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            mapping = root / "mapping.csv"
            mapping.write_text(
                "isin,company_name,nse_symbol,bse_symbol\n", encoding="utf-8"
            )
            paths = {}
            for index in range(1, 5):
                strategy = f"strategy_{index}"
                path = root / f"{strategy}.csv"
                pd.DataFrame([{
                    "Symbol": "ABC", "ISIN": "INE000A01000",
                    "Statement Type": "Consolidated",
                    "Financial Period": "2023-12-31",
                    "Publication Date": "2024-01-05",
                    "ROCE": 20,
                }]).to_csv(path, index=False)
                paths[strategy] = path
            database = root / "screening.sqlite3"
            outputs = run_ingestion(
                FakeUniverse(), FakePrices(), paths,
                {
                    "security_master_path": str(mapping),
                    "technical_workers": 2,
                    "database_path": str(database),
                },
                root / "normalized",
            )
            stocks = pd.read_csv(outputs["stocks"])
            prices = pd.read_csv(outputs["prices"])
            self.assertEqual(len(stocks), 2)
            self.assertEqual(len(prices), 6)
            no_financials = stocks.loc[stocks["isin"] == "INE000B01000"].iloc[0]
            self.assertEqual(no_financials["financial_data_quality_score"], 0)
            self.assertIn("roce", no_financials["financial_data_missing_fields"])
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM price_bars").fetchone()[0], 6
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fundamental_observations"
                    ).fetchone()[0],
                    1,
                )


if __name__ == "__main__":
    unittest.main()

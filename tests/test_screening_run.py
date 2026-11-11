import argparse
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from app import run


class ScreeningRunTests(unittest.TestCase):
    def test_run_writes_five_screens_final_exports_and_historical_snapshot(self):
        class FakeUniverse:
            def nifty500(self):
                return pd.DataFrame([
                    {
                        "symbol": "ABC",
                        "isin": "INE000A01000",
                        "nse_symbol": "ABC",
                        "bse_symbol": pd.NA,
                        "nifty_name": "ABC Ltd",
                    },
                    {
                        "symbol": "XYZ",
                        "isin": "INE000B01000",
                        "nse_symbol": "XYZ",
                        "bse_symbol": pd.NA,
                        "nifty_name": "XYZ Ltd",
                    },
                ])

        class FakePrices:
            def __init__(self, period):
                self.period = period

            def history(self, symbol):
                close = np.linspace(100, 70, 40)
                return pd.DataFrame({
                    "Open": close,
                    "High": close + 1,
                    "Low": close - 1,
                    "Close": close,
                    "Adj Close": close,
                    "Volume": np.full(40, 100000),
                }, index=pd.bdate_range("2025-01-01", periods=40))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            mapping = root / "mapping.csv"
            mapping.write_text(
                "isin,company_name,nse_symbol,bse_symbol\n", encoding="utf-8"
            )
            database = root / "screening.sqlite3"
            settings = root / "settings.yaml"
            settings.write_text(
                f"database_path: {database}\n"
                f"security_master_path: {mapping}\n"
                "technical_workers: 1\nhistory_period: 1y\n",
                encoding="utf-8",
            )
            base_row = {
                "Symbol": "ABC",
                "ISIN": "INE000A01000",
                "Statement Type": "Consolidated",
                "Financial Period": "2025-03-31",
                "Publication Date": "2025-05-01",
                "Market Cap": 15000,
                "ROCE": 25,
                "ROE": 20,
                "Debt to Equity": 0.2,
                "Sales Growth 3Years": 15,
                "Profit Growth 3Years": 15,
                "Quarterly Sales Growth": 12,
                "Quarterly Profit Growth": 12,
                "Operating Cash Flow 3Years": 100,
                "Promoter Holding": 55,
                "Stock P/E": 20,
            }
            weak_row = {
                **base_row,
                "Symbol": "XYZ",
                "ISIN": "INE000B01000",
                "Market Cap": 500,
                "ROCE": 5,
                "ROE": 5,
                "Debt to Equity": 1.1,
                "Sales Growth 3Years": 0,
                "Profit Growth 3Years": 0,
                "Quarterly Sales Growth": 0,
                "Quarterly Profit Growth": 0,
                "Operating Cash Flow 3Years": -1,
                "Promoter Holding": 20,
                "Stock P/E": 50,
            }
            inputs = {}
            for number in range(1, 5):
                path = root / f"strategy{number}.csv"
                pd.DataFrame([base_row, weak_row]).to_csv(path, index=False)
                inputs[f"strategy_{number}"] = path

            workbook = root / "screening_results.xlsx"
            results_dir = root / "strategy_results"
            args = argparse.Namespace(
                **inputs,
                output=str(workbook),
                strategy_results_dir=str(results_dir),
                settings=str(settings),
            )
            with patch("app.NSEProvider", return_value=FakeUniverse()), \
                    patch("app.YahooProvider", FakePrices):
                run(args)

            with pd.ExcelFile(workbook) as excel_file:
                sheets = excel_file.sheet_names
            self.assertTrue({
                "Quality_Correction", "Deep_Value", "Recovery_30_50",
                "Technical_Reversal", "Final_Ranking",
            }.issubset(sheets))
            final = pd.read_excel(workbook, sheet_name="Final_Ranking")
            self.assertEqual(final["symbol"].tolist(), ["ABC"])
            self.assertEqual(final.loc[0, "strategy_membership_count"], 2)
            self.assertTrue(pd.isna(final.loc[0, "fair_value_estimate"]))
            self.assertEqual(
                pd.read_csv(results_dir / "Final_Ranking.csv")["symbol"].tolist(),
                ["ABC"],
            )
            self.assertEqual(
                pd.read_csv(results_dir / "strategy_1_results.csv")["symbol"].tolist(),
                ["ABC"],
            )
            self.assertEqual(
                pd.read_csv(results_dir / "strategy_3_results.csv")["symbol"].tolist(),
                ["ABC"],
            )
            with closing(sqlite3.connect(database)) as connection:
                snapshots = connection.execute(
                    "SELECT combined_score, payload FROM screening_results"
                ).fetchall()
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(
                sorted(json.loads(payload)["strategy_membership_count"] for _, payload in snapshots),
                [0, 2],
            )
            self.assertEqual(
                sorted(json.loads(payload)["rank"] is None for _, payload in snapshots),
                [False, True],
            )


if __name__ == "__main__":
    unittest.main()

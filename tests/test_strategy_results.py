import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from screen_strategy import run
from strategies.screen_results import write_strategy_results


class StrategyResultTests(unittest.TestCase):
    def test_writes_rule_matches_to_separate_strategy_csvs(self):
        strong = {
            "symbol": "STRONG",
            "name": "Strong Company",
            "market_cap": 2000,
            "roce": 20,
            "roe": 18,
            "debt_equity": 0.3,
            "sales_growth": 15,
            "profit_growth": 15,
            "operating_cash_flow": 10,
            "pe": 20,
            "market_price": 70,
            "price_high_1y": 100,
            "rsi14": 40,
            "macd_bullish": np.bool_(True),
            "above_sma20": np.bool_(True),
            "volume_ratio_20d": 1.6,
        }
        falling_weak = {
            **strong,
            "symbol": "WEAK",
            "market_cap": 800,
            "roce": 5,
            "roe": 5,
            "debt_equity": 1.2,
            "sales_growth": -10,
            "profit_growth": -10,
            "operating_cash_flow": -5,
            "market_price": 40,
            "macd_bullish": False,
            "above_sma20": False,
            "volume_ratio_20d": 0.8,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_strategy_results(
                pd.DataFrame([strong, falling_weak]), temp_dir
            )

            self.assertEqual(set(paths), {
                "strategy_1", "strategy_2", "strategy_3", "strategy_4"
            })
            results = {
                strategy: pd.read_csv(path)
                for strategy, path in paths.items()
            }

        self.assertEqual(results["strategy_1"]["symbol"].tolist(), ["STRONG"])
        self.assertEqual(results["strategy_2"]["symbol"].tolist(), [])
        self.assertEqual(results["strategy_3"]["symbol"].tolist(), ["STRONG"])
        self.assertEqual(results["strategy_4"]["symbol"].tolist(), ["STRONG"])
        self.assertTrue(
            (results["strategy_4"]["strategy_rule"] == "strategy_4").all()
        )

    def test_single_strategy_command_writes_only_selected_matches(self):
        source_rows = pd.DataFrame([{
            "symbol": "STRONG",
            "name": "Strong Company",
            "isin": pd.NA,
            "market_cap": 2000,
            "roce": 20,
            "roe": 18,
            "debt_equity": 0.3,
            "sales_growth": 15,
            "profit_growth": 15,
            "operating_cash_flow": 10,
            "pe": 20,
            "financial_basis": "consolidated",
        }])
        universe = pd.DataFrame([{
            "symbol": "STRONG",
            "isin": "INE123A01016",
            "nifty_name": "Strong Company",
        }])

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "strategy1.csv"
            input_path.write_text("placeholder", encoding="utf-8")
            output_path = Path(temp_dir) / "results" / "strategy_1_results.csv"
            with patch("screen_strategy.read_screener", return_value=source_rows), \
                    patch("screen_strategy.NSEProvider") as nse_provider:
                nse_provider.return_value.nifty500.return_value = universe
                result_path = run(
                    "strategy_1", input_path, output_path, "missing-settings.yaml"
                )
            result = pd.read_csv(result_path)

        self.assertEqual(result["symbol"].tolist(), ["STRONG"])
        self.assertEqual(result["isin"].tolist(), ["INE123A01016"])
        self.assertEqual(result["strategy_rule"].tolist(), ["strategy_1"])


if __name__ == "__main__":
    unittest.main()

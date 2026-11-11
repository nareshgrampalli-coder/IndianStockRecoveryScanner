import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

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


if __name__ == "__main__":
    unittest.main()

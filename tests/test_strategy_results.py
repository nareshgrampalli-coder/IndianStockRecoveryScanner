import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from screen_strategy import run
from strategies.screen_results import matching_rows, write_strategy_results


class StrategyResultTests(unittest.TestCase):
    def test_strategy_evaluation_shows_named_progress_bar(self):
        progress = {}

        def capture_progress(iterable, **kwargs):
            progress.update(kwargs)
            return iterable

        with patch("strategies.screen_results.tqdm", side_effect=capture_progress):
            matching_rows(pd.DataFrame([{"symbol": "TEST"}]), "strategy_2")

        self.assertEqual(progress["desc"], "Evaluating Deep Value")
        self.assertEqual(progress["total"], 1)
        self.assertEqual(progress["unit"], "stock")

    def test_strategy_two_requires_market_cap_above_10000(self):
        baseline = {
            "symbol": "PASS",
            "market_cap": 10001,
            "market_price": 49,
            "price_high_1y": 100,
            "roce": 13,
            "roe": 11,
            "debt_equity": 0.6,
            "sales_growth": 6,
            "profit_growth": 6,
            "operating_cash_flow": 1,
            "pe": 24,
        }
        candidates = pd.DataFrame([
            baseline,
            {**baseline, "symbol": "AT-CAP-THRESHOLD", "market_cap": 10000},
        ])

        result = matching_rows(candidates, "strategy_2")

        self.assertEqual(result["symbol"].tolist(), ["PASS"])

    def test_strategy_three_requires_quarterly_growth_and_promoter_holding(self):
        baseline = {
            "symbol": "PASS",
            "market_cap": 15000,
            "market_price": 74,
            "price_high_1y": 100,
            "roce": 16,
            "roe": 13,
            "debt_equity": 0.49,
            "sales_growth": 11,
            "profit_growth": 11,
            "quarterly_sales_growth": 11,
            "quarterly_profit_growth": 11,
            "pe": 29,
            "promoter_holding": 31,
        }
        candidates = pd.DataFrame([
            baseline,
            {**baseline, "symbol": "LOW-QUARTERLY", "quarterly_sales_growth": 10},
            {**baseline, "symbol": "LOW-PROMOTER", "promoter_holding": 30},
            {**baseline, "symbol": "AT-CAP-THRESHOLD", "market_cap": 10000},
        ])

        result = matching_rows(candidates, "strategy_3")

        self.assertEqual(result["symbol"].tolist(), ["PASS"])

    def test_strategy_four_applies_fundamental_price_and_technical_conditions(self):
        baseline = {
            "symbol": "PASS",
            "market_cap": 15000,
            "market_price": 79,
            "price_high_1y": 100,
            "roce": 13,
            "debt_equity": 0.6,
            "sales_growth": 6,
            "profit_growth": 6,
            "quarterly_profit_growth": 1,
            "pe": 34,
            "rsi14": 40,
            "macd_bullish": True,
            "above_ema20": True,
            "volume_ratio_20d": 1.6,
        }
        candidates = pd.DataFrame([
            baseline,
            {**baseline, "symbol": "NO-QUARTERLY-GROWTH", "quarterly_profit_growth": 0},
            {**baseline, "symbol": "AT-PRICE-LIMIT", "market_price": 80},
            {**baseline, "symbol": "RSI-OUTSIDE-RANGE", "rsi14": 46},
            {**baseline, "symbol": "AT-CAP-THRESHOLD", "market_cap": 10000},
        ])

        result = matching_rows(candidates, "strategy_4")

        self.assertEqual(result["symbol"].tolist(), ["PASS"])

    def test_writes_rule_matches_to_separate_strategy_csvs(self):
        strong = {
            "symbol": "STRONG",
            "name": "Strong Company",
            "market_cap": 15000,
            "roce": 20,
            "roe": 18,
            "debt_equity": 0.3,
            "sales_growth": 15,
            "profit_growth": 15,
            "quarterly_sales_growth": 15,
            "quarterly_profit_growth": 15,
            "operating_cash_flow": 10,
            "promoter_holding": 40,
            "pe": 20,
            "market_price": 70,
            "price_high_1y": 100,
            "rsi14": 40,
            "macd_bullish": np.bool_(True),
            "above_ema20": np.bool_(True),
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
            "above_ema20": False,
            "volume_ratio_20d": 0.8,
        }
        no_correction = {**strong, "symbol": "NO-CORRECTION", "market_price": 75}
        low_promoter_holding = {
            **strong, "symbol": "LOW-PROMOTER", "promoter_holding": 35
        }
        at_market_cap_threshold = {
            **strong, "symbol": "AT-CAP-THRESHOLD", "market_cap": 10000
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_strategy_results(
                pd.DataFrame([
                    strong, falling_weak, no_correction, low_promoter_holding,
                    at_market_cap_threshold,
                ]),
                temp_dir,
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
        self.assertEqual(
            results["strategy_3"]["symbol"].tolist(),
            ["STRONG", "LOW-PROMOTER"],
        )
        self.assertEqual(
            results["strategy_4"]["symbol"].tolist(),
            ["STRONG", "NO-CORRECTION", "LOW-PROMOTER"],
        )
        self.assertTrue(
            (results["strategy_4"]["strategy_rule"] == "strategy_4").all()
        )

    def test_single_strategy_command_writes_only_selected_matches(self):
        source_rows = pd.DataFrame([{
            "symbol": "STRONG",
            "name": "Strong Company",
            "isin": pd.NA,
            "market_cap": 15000,
            "roce": 20,
            "roe": 18,
            "debt_equity": 0.3,
            "sales_growth": 15,
            "profit_growth": 15,
            "operating_cash_flow": 10,
            "promoter_holding": 40,
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
                    patch("screen_strategy.NSEProvider") as nse_provider, \
                    patch(
                        "screen_strategy.technicals_for",
                        return_value=({"market_price": 50, "price_high_1y": 100}, []),
                    ):
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

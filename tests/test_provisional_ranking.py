import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data_processing.provisional_ranking import (
    build_provisional_ranking, read_copied_screener_screens,
)


class ProvisionalRankingTests(unittest.TestCase):
    def test_reads_pasted_tables_merges_companies_and_filters_market_cap(self):
        headers = [
            "S.No.", "Company", "CMP Rs.", "P/E", "Mar Cap Rs.Cr.",
            "Div Yld %", "Payout ratio %", "NP Qtr Rs.Cr.",
            "Qtr Profit Var %", "Sales Qtr Rs.Cr.", "Qtr Sales Var %",
            "ROCE %", "ROE %", "52w High Rs.", "Vol 1d", "1day return %",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "data" / "inputs"
            results_dir = root / "strategy_results"
            input_dir.mkdir(parents=True)
            results_dir.mkdir(parents=True)

            pd.DataFrame([
                ["1.", "Quality Company", 50, 20, 12000, 4, 50, 10, 20, 100, 15, 20, 18, 100, 1500, 2],
                ["2.", "Threshold Company", 50, 20, 10000, 4, 50, 10, 20, 100, 15, 20, 18, 100, 1500, 2],
            ], columns=headers).to_csv(
                input_dir / "quality_correction.csv", sep="\t", index=False
            )
            pd.DataFrame([
                ["1.", "Quality Co.", 52, 22, 12002, 3, 60, 11, 10, 101, 5, 15, 15, 100, 1200, 1.5],
            ], columns=headers).to_csv(
                results_dir / "deep_value_results.csv", sep="\t", index=False
            )
            for name in ("recovery_30_50", "technical_reversal"):
                pd.DataFrame(columns=headers).to_csv(
                    results_dir / f"{name}_results.csv", sep="\t", index=False
                )

            output_path = root / "partial_analysis" / "ranking.csv"
            ranking = build_provisional_ranking(input_dir, results_dir, output_path)

            self.assertTrue(output_path.is_file())
            self.assertEqual(ranking["company"].tolist(), ["Quality Company"])
            self.assertEqual(ranking.loc[0, "market_cap"], 12001)
            self.assertTrue(ranking.loc[0, "market_cap_over_10000"])
            self.assertEqual(ranking.loc[0, "count_source_rows"], 2)
            self.assertEqual(
                ranking.loc[0, "source_strategies"],
                "deep_value;quality_correction",
            )
            self.assertEqual(ranking.loc[0, "provisional_component_coverage_pct"], 100)
            self.assertEqual(ranking.loc[0, "quarterly_net_profit"], 10.5)
            self.assertEqual(ranking.loc[0, "quarterly_sales"], 100.5)
            self.assertEqual(ranking.loc[0, "daily_volume"], 1350)
            self.assertEqual(ranking.loc[0, "daily_return_pct"], 1.75)
            self.assertEqual(ranking.loc[0, "dividend_yield"], 3.5)
            self.assertEqual(ranking.loc[0, "payout_ratio"], 55)
            self.assertAlmostEqual(
                ranking.loc[0, "quarterly_net_margin_pct"], 10.4478, places=3
            )
            saved = pd.read_csv(output_path)
            self.assertTrue((saved["market_cap"] > 10000).all())
            self.assertNotIn("Threshold Company", saved["company"].tolist())

    def test_empty_strategy_table_does_not_block_other_strategies(self):
        headers = [
            "S.No.", "Company", "CMP Rs.", "P/E", "Mar Cap Rs.Cr.",
            "ROCE %", "ROE %", "52w High Rs.",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "data" / "inputs"
            results_dir = root / "strategy_results"
            input_dir.mkdir(parents=True)
            results_dir.mkdir(parents=True)

            pd.DataFrame([
                ["1.", "Quality Company", 50, 20, 12000, 20, 18, 100],
            ], columns=headers).to_csv(
                results_dir / "quality_correction_results.csv",
                sep="\t",
                index=False,
            )
            (results_dir / "deep_value_results.csv").write_bytes(b"")
            for name in ("recovery_30_50", "technical_reversal"):
                pd.DataFrame(columns=headers).to_csv(
                    results_dir / f"{name}_results.csv",
                    sep="\t",
                    index=False,
                )

            screens = read_copied_screener_screens(input_dir, results_dir)
            ranking = build_provisional_ranking(
                input_dir,
                results_dir,
                root / "partial_analysis" / "ranking.csv",
            )

        self.assertEqual(
            [screen["title"] for screen in screens],
            [
                "Quality Correction", "Deep Value",
                "Recovery 30-50", "Technical Reversal",
            ],
        )
        self.assertEqual([len(screen["rows"]) for screen in screens], [1, 0, 0, 0])
        self.assertIn("Company", screens[0]["columns"])
        self.assertEqual(ranking["company"].tolist(), ["Quality Company"])


if __name__ == "__main__":
    unittest.main()

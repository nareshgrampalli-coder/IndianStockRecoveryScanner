import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data_processing.provisional_ranking import build_provisional_ranking


class ProvisionalRankingTests(unittest.TestCase):
    def test_reads_pasted_tables_merges_companies_and_filters_market_cap(self):
        headers = [
            "S.No.", "Company", "CMP Rs.", "P/E", "Mar Cap Rs.Cr.",
            "Qtr Profit Var %", "Qtr Sales Var %", "ROCE %", "ROE %",
            "52w High Rs.",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "data" / "inputs"
            results_dir = root / "strategy_results"
            input_dir.mkdir(parents=True)
            results_dir.mkdir(parents=True)

            pd.DataFrame([
                ["1.", "Quality Company", 50, 20, 12000, 20, 15, 20, 18, 100],
                ["2.", "Threshold Company", 50, 20, 10000, 20, 15, 20, 18, 100],
            ], columns=headers).to_csv(
                input_dir / "quality_correction.csv", sep="\t", index=False
            )
            pd.DataFrame([
                ["1.", "Quality Co.", 52, 22, 12002, 10, 5, 15, 15, 100],
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

            ranking = build_provisional_ranking(
                input_dir,
                results_dir,
                root / "partial_analysis" / "ranking.csv",
            )

        self.assertEqual(ranking["company"].tolist(), ["Quality Company"])


if __name__ == "__main__":
    unittest.main()

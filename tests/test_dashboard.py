import unittest

import pandas as pd

from dashboard import build_dashboard_payload, build_provisional_payload


class DashboardTests(unittest.TestCase):
    def test_dashboard_reports_final_ranking_and_retains_research_funnel(self):
        frame = pd.DataFrame([
            {
                "rank": 1, "symbol": "AAA", "name": "Alpha",
                "strategy_3_primary": True, "strategy_1_quality": True,
                "strategy_4_entry_timing": True, "strategy_2_deep_value": False,
                "combined_score": 90,
            },
            {
                "rank": 2, "symbol": "BBB", "name": "Beta",
                "strategy_3_primary": True, "strategy_1_quality": True,
                "strategy_4_entry_timing": False, "strategy_2_deep_value": True,
                "combined_score": 80,
            },
            {
                "rank": 3, "symbol": "CCC", "name": "Gamma",
                "strategy_3_primary": True, "strategy_1_quality": False,
                "strategy_4_entry_timing": True, "strategy_2_deep_value": False,
                "combined_score": 70,
            },
            {
                "rank": 4, "symbol": "DDD", "name": "Delta",
                "strategy_3_primary": False, "strategy_1_quality": True,
                "strategy_4_entry_timing": True, "strategy_2_deep_value": True,
                "combined_score": 60,
            },
        ])

        payload = build_dashboard_payload(frame)
        self.assertEqual(payload["counts"]["strategy_3_primary"], 3)
        self.assertEqual(payload["counts"]["after_quality_filter"], 2)
        self.assertEqual(payload["counts"]["after_entry_timing_filter"], 1)
        self.assertEqual(payload["counts"]["final_ranking"], 4)
        self.assertEqual(
            [row["symbol"] for row in payload["final_candidates"]],
            ["AAA", "BBB", "CCC", "DDD"],
        )

    def test_provisional_dashboard_payload_keeps_partial_coverage_and_threshold(self):
        payload = build_provisional_payload(pd.DataFrame([
            {
                "rank": 2, "company": "Beta", "provisional_score": 80,
                "provisional_component_coverage_pct": 80,
                "market_cap_over_10000": False,
                "source_strategies": "deep_value",
            },
            {
                "rank": 1, "company": "Alpha", "provisional_score": 95,
                "provisional_component_coverage_pct": 100,
                "market_cap_over_10000": True,
                "source_strategies": "quality_correction",
            },
        ]))

        self.assertEqual(payload["summary"]["companies"], 2)
        self.assertEqual(payload["summary"]["below_market_cap_threshold"], 1)
        self.assertEqual(
            [row["company"] for row in payload["stocks"]],
            ["Alpha", "Beta"],
        )


if __name__ == "__main__":
    unittest.main()

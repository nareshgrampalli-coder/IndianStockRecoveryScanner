import unittest

import pandas as pd

from dashboard import build_dashboard_payload


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


if __name__ == "__main__":
    unittest.main()

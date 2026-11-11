import unittest

import pandas as pd

from scoring.weighted_score import WEIGHTS, add_weighted_score, score_price_correction


class WeightedScoringTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "roce_score": 100,
            "roe_score": 100,
            "cash_flow_score": 100,
            "sales_growth_score": 100,
            "earnings_growth_score": 100,
            "valuation_score": 100,
            "technical_score": 100,
            "market_price": 50,
            "price_high_1y": 100,
            "debt_equity": 0.1,
            "promoter_holding": 60,
            "promoter_pledging": 0,
        }

    def test_weights_total_100_and_full_score(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)
        scored = add_weighted_score(pd.DataFrame([self.row])).iloc[0]
        self.assertEqual(scored["combined_score"], 100)
        self.assertEqual(scored["score_coverage_pct"], 100)

    def test_missing_components_renormalize_available_weights(self):
        row = dict(self.row, technical_score=float("nan"),
                   market_price=float("nan"), price_high_1y=float("nan"))
        scored = add_weighted_score(pd.DataFrame([row])).iloc[0]
        self.assertEqual(scored["combined_score"], 100)
        self.assertEqual(scored["score_coverage_pct"], 70)

    def test_correction_score_uses_documented_bands(self):
        scores = score_price_correction(
            pd.Series([75, 50, 65, 90]), pd.Series([100, 100, 100, 100])
        )
        self.assertEqual(scores.tolist(), [50, 100, 75, 0])


if __name__ == "__main__":
    unittest.main()

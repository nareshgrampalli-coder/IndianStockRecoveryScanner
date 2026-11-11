import unittest

import pandas as pd

from scoring.weighted_score import (
    STRATEGY_WEIGHTS,
    WEIGHTS,
    add_weighted_score,
    score_price_correction,
)


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
            "rsi_score": 100,
            "macd_score": 100,
            "moving_average_score": 100,
            "volume_score": 100,
            "support_score": 100,
            "market_price": 50,
            "price_high_1y": 100,
            "debt_equity": 0.1,
            "promoter_holding": 60,
            "promoter_pledging": 0,
            "strategy": "strategy_1",
        }

    def test_each_strategy_weight_profile_totals_100(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)
        for weights in STRATEGY_WEIGHTS.values():
            self.assertEqual(sum(weights.values()), 100)

    def test_full_strategy_score(self):
        scored = add_weighted_score(pd.DataFrame([self.row])).iloc[0]
        self.assertEqual(scored["combined_score"], 100)
        self.assertEqual(scored["score_coverage_pct"], 100)

    def test_missing_components_renormalize_available_weights(self):
        row = dict(self.row, technical_score=float("nan"), rsi_score=float("nan"),
                   macd_score=float("nan"), moving_average_score=float("nan"),
                   volume_score=float("nan"), support_score=float("nan"),
                   market_price=float("nan"), price_high_1y=float("nan"))
        scored = add_weighted_score(pd.DataFrame([row])).iloc[0]
        self.assertEqual(scored["combined_score"], 100)
        self.assertEqual(scored["score_coverage_pct"], 70)

    def test_correction_is_gated_by_business_recovery_evidence(self):
        row = dict(self.row, roce_score=0, roe_score=0, cash_flow_score=0,
                   sales_growth_score=0, earnings_growth_score=0)
        scored = add_weighted_score(pd.DataFrame([row])).iloc[0]
        self.assertEqual(scored["price_correction_score"], 0)
        missing = dict(row, roce_score=float("nan"), roe_score=float("nan"),
                       cash_flow_score=float("nan"), sales_growth_score=float("nan"),
                       earnings_growth_score=float("nan"))
        scored_missing = add_weighted_score(pd.DataFrame([missing])).iloc[0]
        self.assertTrue(pd.isna(scored_missing["price_correction_score"]))

    def test_overlapping_memberships_average_profile_scores(self):
        row = dict(self.row, strategy="strategy_2, strategy_4",
                   valuation_score=100, technical_score=50, rsi_score=0,
                   macd_score=0, moving_average_score=0, volume_score=100,
                   support_score=0)
        scored = add_weighted_score(pd.DataFrame([row])).iloc[0]
        expected = (scored["strategy_2_score"] + scored["strategy_4_score"]) / 2
        self.assertEqual(scored["combined_score"], expected)
        self.assertGreater(scored["strategy_4_score_coverage_pct"], 0)

    def test_deep_value_profile_rewards_valuation_more(self):
        row = dict(
            self.row,
            strategy="strategy_1, strategy_2",
            roce_score=0,
            roe_score=0,
            cash_flow_score=0,
            sales_growth_score=0,
            earnings_growth_score=0,
            valuation_score=100,
            technical_score=0,
            rsi_score=0,
            macd_score=0,
            moving_average_score=0,
            volume_score=0,
            support_score=0,
            debt_equity=2,
            promoter_holding=10,
            promoter_pledging=100,
        )
        frame = pd.DataFrame([row])
        scored = add_weighted_score(frame).iloc[0]
        self.assertGreater(scored["strategy_2_score"], scored["strategy_1_score"])

    def test_correction_score_uses_documented_bands(self):
        scores = score_price_correction(
            pd.Series([75, 50, 65, 90]), pd.Series([100, 100, 100, 100])
        )
        self.assertEqual(scores.tolist(), [50, 100, 75, 0])


if __name__ == "__main__":
    unittest.main()

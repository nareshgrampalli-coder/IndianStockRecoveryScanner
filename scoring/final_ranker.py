import pandas as pd

from scoring.weighted_score import add_weighted_score


def rank_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    strategies = frame["strategy"].fillna("").str.split(", ")
    frame["strategy_3_primary"] = strategies.map(lambda values: "strategy_3" in values)
    frame["strategy_1_quality"] = strategies.map(lambda values: "strategy_1" in values)
    frame["strategy_4_entry_timing"] = strategies.map(lambda values: "strategy_4" in values)
    frame["strategy_2_deep_value"] = strategies.map(lambda values: "strategy_2" in values)
    frame = add_weighted_score(frame)
    frame = frame.sort_values(
        ["combined_score", "score_coverage_pct", "financial_quality_score"],
        ascending=False, na_position="last",
    )
    frame.insert(0, "rank", range(1, len(frame) + 1))
    frame["research_shortlist"] = frame["rank"] <= 15
    return frame

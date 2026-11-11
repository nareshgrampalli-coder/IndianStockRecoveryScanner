import pandas as pd


def rank_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    strategies = frame["strategy"].fillna("").str.split(", ")
    frame["strategy_3_primary"] = strategies.map(lambda values: "strategy_3" in values)
    frame["strategy_1_quality"] = strategies.map(lambda values: "strategy_1" in values)
    frame["strategy_4_entry_timing"] = strategies.map(lambda values: "strategy_4" in values)
    frame["strategy_2_deep_value"] = strategies.map(lambda values: "strategy_2" in values)
    frame["combined_score"] = frame[["fundamental_score", "technical_score"]].mean(axis=1)
    frame = frame.sort_values(
        ["combined_score", "strategy_3_primary", "strategy_1_quality",
         "strategy_4_entry_timing", "fundamental_score"],
        ascending=False, na_position="last",
    )
    frame.insert(0, "rank", range(1, len(frame) + 1))
    frame["research_shortlist"] = frame["rank"] <= 15
    return frame

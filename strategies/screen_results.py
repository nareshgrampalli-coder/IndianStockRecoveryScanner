from pathlib import Path

import pandas as pd
from tqdm import tqdm

from strategies.deep_value import matches as deep_value_matches
from strategies.quality_correction import matches as quality_correction_matches
from strategies.recovery_30_50 import matches as recovery_30_50_matches
from strategies.technical_reversal import matches as technical_reversal_matches

MATCHERS = {
    "strategy_1": quality_correction_matches,
    "strategy_2": deep_value_matches,
    "strategy_3": recovery_30_50_matches,
    "strategy_4": technical_reversal_matches,
}
DISPLAY_NAMES = {
    "strategy_1": "Quality_Correction",
    "strategy_2": "Deep_Value",
    "strategy_3": "Recovery_30_50",
    "strategy_4": "Technical_Reversal",
}
STRATEGY_NAMES = {
    strategy: name.replace("_", " ")
    for strategy, name in DISPLAY_NAMES.items()
}


def matching_rows(candidates: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """Return candidate rows that satisfy one strategy's implemented conditions."""
    try:
        matcher = MATCHERS[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {strategy}") from exc

    matched_indices = []
    for index, row in tqdm(
        candidates.iterrows(),
        total=len(candidates),
        desc=f"Evaluating {STRATEGY_NAMES[strategy]}",
        unit="stock",
    ):
        rule_row = row.to_dict()
        rule_row["52_week_high"] = row.get("price_high_1y")
        if strategy == "strategy_4":
            rule_row["macd_bullish"] = (
                str(row.get("macd_bullish", "")).strip().lower() == "true"
            )
            rule_row["above_ema20"] = (
                str(row.get("above_ema20", "")).strip().lower() == "true"
            )
        if matcher(rule_row):
            matched_indices.append(index)
    return candidates.loc[matched_indices].copy()


def add_strategy_matches(candidates: pd.DataFrame) -> pd.DataFrame:
    """Apply all four screen rules and make those results the canonical memberships."""
    result = candidates.copy()
    members = {}
    for strategy in MATCHERS:
        matched = matching_rows(result, strategy)
        column = f"{strategy}_screen_pass"
        result[column] = result.index.isin(matched.index)
        members[strategy] = result[column]
    result["strategy"] = result.apply(
        lambda row: ", ".join(
            strategy for strategy in MATCHERS if row[f"{strategy}_screen_pass"]
        ),
        axis=1,
    )
    result["strategy_membership"] = result["strategy"].map(
        lambda value: ", ".join(
            DISPLAY_NAMES[strategy] for strategy in value.split(", ") if strategy
        )
    )
    return result


def write_strategy_results(
    candidates: pd.DataFrame, output_dir: str | Path
) -> dict[str, Path]:
    """Write one CSV containing the candidates matching each strategy's rules."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for strategy in MATCHERS:
        membership_column = f"{strategy}_screen_pass"
        if membership_column in candidates.columns:
            result = candidates[candidates[membership_column]].copy()
        else:
            result = matching_rows(candidates, strategy)
        result["strategy_rule"] = strategy
        path = output_dir / f"{strategy}_results.csv"
        result.to_csv(path, index=False)
        results[strategy] = path

    return results

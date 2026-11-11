from pathlib import Path

import pandas as pd

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


def matching_rows(candidates: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """Return candidate rows that satisfy one strategy's implemented conditions."""
    try:
        matcher = MATCHERS[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {strategy}") from exc

    matched = []
    for row in candidates.to_dict("records"):
        rule_row = dict(row)
        rule_row["52_week_high"] = row.get("price_high_1y")
        if strategy == "strategy_4":
            rule_row["macd_bullish"] = (
                str(row.get("macd_bullish", "")).strip().lower() == "true"
            )
            rule_row["above_ema20"] = (
                str(row.get("above_ema20", "")).strip().lower() == "true"
            )
        if matcher(rule_row):
            matched.append(row)
    return pd.DataFrame(matched, columns=candidates.columns)


def write_strategy_results(
    candidates: pd.DataFrame, output_dir: str | Path
) -> dict[str, Path]:
    """Write one CSV containing the candidates matching each strategy's rules."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for strategy in MATCHERS:
        result = matching_rows(candidates, strategy)
        result["strategy_rule"] = strategy
        path = output_dir / f"{strategy}_results.csv"
        result.to_csv(path, index=False)
        results[strategy] = path

    return results

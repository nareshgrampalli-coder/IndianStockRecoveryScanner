"""Strategy-specific weighted scores with missing-data renormalization."""

import pandas as pd

WEIGHTS = {
    "financial_quality_score": 20,
    "earnings_growth_component_score": 20,
    "valuation_attractiveness_score": 15,
    "technical_recovery_score": 20,
    "recovery_potential_score": 15,
    "risk_governance_score": 10,
}
STRATEGY_WEIGHTS = {
    "strategy_1": {
        "financial_quality_score": 25,
        "earnings_growth_component_score": 20,
        "valuation_attractiveness_score": 15,
        "technical_recovery_score": 20,
        "recovery_potential_score": 10,
        "risk_governance_score": 10,
    },
    "strategy_2": {
        "financial_quality_score": 20,
        "earnings_growth_component_score": 15,
        "valuation_attractiveness_score": 25,
        "technical_recovery_score": 15,
        "recovery_potential_score": 10,
        "risk_governance_score": 15,
    },
    "strategy_3": {
        "financial_quality_score": 25,
        "earnings_growth_component_score": 25,
        "valuation_attractiveness_score": 15,
        "technical_recovery_score": 15,
        "recovery_potential_score": 10,
        "risk_governance_score": 10,
    },
    "strategy_4": {
        "financial_quality_score": 15,
        "earnings_growth_component_score": 15,
        "valuation_attractiveness_score": 10,
        "technical_recovery_score": 35,
        "recovery_potential_score": 15,
        "risk_governance_score": 10,
    },
}


def score_price_correction(price: pd.Series, high: pd.Series) -> pd.Series:
    drawdown_pct = (1 - price / high) * 100
    return drawdown_pct.map(
        lambda value: 100 if value >= 50 else 75 if value >= 35 else
        50 if value >= 25 else 25 if value >= 15 else 0
        if pd.notna(value) else float("nan")
    ).where(high.gt(0) & price.notna())


def _weighted_average(frame: pd.DataFrame, weights: dict[str, int]) -> tuple[pd.Series, pd.Series]:
    columns = list(weights)
    values = frame[columns]
    available_weights = values.notna().mul(pd.Series(weights)).sum(axis=1)
    points = values.mul(pd.Series(weights)).sum(axis=1, min_count=1)
    score = (points / available_weights).where(available_weights.gt(0))
    return score, available_weights


def add_weighted_score(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["financial_quality_score"] = frame[
        ["roce_score", "roe_score", "cash_flow_score"]
    ].mean(axis=1, skipna=True)
    frame["earnings_growth_component_score"] = frame[
        ["sales_growth_score", "earnings_growth_score"]
    ].mean(axis=1, skipna=True)
    frame["valuation_attractiveness_score"] = frame["valuation_score"]
    frame["technical_recovery_score"] = frame["technical_score"]
    raw_correction = score_price_correction(
        frame["market_price"], frame["price_high_1y"]
    )
    recovery_evidence = frame[
        ["financial_quality_score", "earnings_growth_component_score"]
    ].mean(axis=1, skipna=True)
    recovery_available = frame[
        ["financial_quality_score", "earnings_growth_component_score"]
    ].notna().any(axis=1)
    frame["recovery_potential_score"] = (
        raw_correction * recovery_evidence / 100
    ).where(recovery_available)
    frame["price_correction_score"] = frame["recovery_potential_score"]
    if "risk_governance_score" not in frame:
        from scoring.risk_score import score_governance
        frame["risk_governance_score"] = score_governance(frame)

    momentum = frame[["rsi_score", "macd_score", "moving_average_score"]]
    momentum_weights = {"rsi_score": 40, "macd_score": 35, "moving_average_score": 25}
    momentum_score, _ = _weighted_average(momentum, momentum_weights)
    reversal_technical, _ = _weighted_average(
        pd.DataFrame({
            "momentum": momentum_score,
            "volume": frame["volume_score"],
            "support": frame["support_score"],
        }, index=frame.index),
        {"momentum": 50, "volume": 30, "support": 20},
    )
    frame["technical_reversal_score"] = reversal_technical

    memberships = frame["strategy"].fillna("").str.split(", ")
    for strategy, weights in STRATEGY_WEIGHTS.items():
        profile = frame[list(weights)].copy()
        if strategy == "strategy_4":
            profile["technical_recovery_score"] = reversal_technical
        score, coverage = _weighted_average(profile, weights)
        member = memberships.map(lambda values: strategy in values)
        score = score.where(member)
        coverage = coverage.where(member)
        score_column = f"{strategy}_score"
        coverage_column = f"{strategy}_score_coverage_pct"
        frame[score_column] = score
        frame[coverage_column] = coverage

    frame["combined_score"], final_coverage = _weighted_average(frame, WEIGHTS)
    frame["score_coverage_pct"] = final_coverage
    frame["strategy_membership_count"] = memberships.map(
        lambda values: sum(strategy in values for strategy in STRATEGY_WEIGHTS)
    )
    frame["multi_strategy_signal"] = frame["strategy_membership_count"].map(
        lambda count: (
            "Multi-screen support" if count > 1
            else "Single-screen" if count == 1
            else "No screen match"
        )
    )
    return frame

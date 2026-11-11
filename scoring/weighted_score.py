"""Weighted 100-point score with proportional redistribution of missing components."""

import pandas as pd

WEIGHTS = {
    "financial_quality_score": 25,
    "earnings_growth_component_score": 20,
    "valuation_attractiveness_score": 15,
    "technical_recovery_score": 20,
    "price_correction_score": 10,
    "risk_governance_score": 10,
}


def score_price_correction(price: pd.Series, high: pd.Series) -> pd.Series:
    drawdown_pct = (1 - price / high) * 100
    return drawdown_pct.map(
        lambda value: 100 if value >= 50 else 75 if value >= 35 else
        50 if value >= 25 else 25 if value >= 15 else 0
        if pd.notna(value) else float("nan")
    ).where(high.gt(0) & price.notna())


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
    frame["price_correction_score"] = score_price_correction(
        frame["market_price"], frame["price_high_1y"]
    )
    if "risk_governance_score" not in frame:
        from scoring.risk_score import score_governance
        frame["risk_governance_score"] = score_governance(frame)

    component_columns = list(WEIGHTS)
    component_values = frame[component_columns]
    available_weights = component_values.notna().mul(
        pd.Series(WEIGHTS)
    ).sum(axis=1)
    weighted_points = component_values.mul(pd.Series(WEIGHTS)).sum(axis=1, min_count=1)
    frame["score_coverage_pct"] = available_weights
    frame["combined_score"] = (weighted_points / available_weights).where(
        available_weights.gt(0)
    )
    return frame

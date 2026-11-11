import pandas as pd

FACTORS = ["roce_score", "roe_score", "sales_growth_score", "earnings_growth_score",
           "debt_score", "cash_flow_score", "valuation_score"]


def score_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    specifications = {
        "roce": (20, 15, 12), "roe": (20, 15, 12),
        "sales_growth": (15, 10, 5), "profit_growth": (15, 10, 5),
    }
    for field, (top, mid, low) in specifications.items():
        frame[{"profit_growth": "earnings_growth_score"}.get(field, f"{field}_score")] = frame[field].map(
            lambda x: 100 if x >= top else 75 if x >= mid else 50 if x >= low else 0
            if pd.notna(x) else float("nan")
        )
    frame["debt_score"] = frame["debt_equity"].map(
        lambda x: 100 if x <= .25 else 75 if x <= .5 else 50 if x <= .7 else 0
        if pd.notna(x) else float("nan")
    )
    frame["cash_flow_score"] = frame["operating_cash_flow"].map(
        lambda x: (100 if x > 0 else 0) if pd.notna(x) else float("nan")
    )
    frame["valuation_score"] = frame["pe"].map(
        lambda x: 100 if 0 < x <= 20 else 75 if 0 < x <= 25 else 50 if 0 < x <= 35 else 0
        if pd.notna(x) else float("nan")
    )
    frame["fundamental_score"] = frame[FACTORS].mean(axis=1, skipna=True)
    frame["fundamentals_available"] = frame[FACTORS].notna().sum(axis=1)
    return frame

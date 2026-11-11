import pandas as pd


def score_debt(debt_equity: pd.Series) -> pd.Series:
    return debt_equity.map(lambda x: 100 if x <= .25 else 75 if x <= .5 else 50 if x <= .7 else 0
                           if pd.notna(x) else float("nan"))


def score_governance(frame: pd.DataFrame) -> pd.Series:
    missing = pd.Series(float("nan"), index=frame.index)
    holding = frame.get("promoter_holding", missing).map(
        lambda x: 100 if x >= 50 else 75 if x >= 35 else 50 if x >= 25 else 25
        if pd.notna(x) else float("nan")
    )
    pledging = frame.get("promoter_pledging", missing).map(
        lambda x: 100 if x <= 0 else 75 if x <= 10 else 50 if x <= 25 else 0
        if pd.notna(x) else float("nan")
    )
    components = pd.concat(
        [score_debt(frame.get("debt_equity", missing)), holding, pledging], axis=1
    )
    return components.mean(axis=1, skipna=True).where(components.notna().any(axis=1))

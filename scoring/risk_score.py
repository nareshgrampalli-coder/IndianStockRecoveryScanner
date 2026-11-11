import pandas as pd


def score_debt(debt_equity: pd.Series) -> pd.Series:
    return debt_equity.map(lambda x: 100 if x <= .25 else 75 if x <= .5 else 50 if x <= .7 else 0
                           if pd.notna(x) else float("nan"))

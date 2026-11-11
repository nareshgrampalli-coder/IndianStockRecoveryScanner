import pandas as pd


def score_valuation(pe: pd.Series) -> pd.Series:
    return pe.map(lambda x: 100 if 0 < x <= 20 else 75 if 0 < x <= 25 else 50 if 0 < x <= 35 else 0
                  if pd.notna(x) else float("nan"))

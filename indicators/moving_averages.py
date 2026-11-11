import pandas as pd


def moving_averages(close: pd.Series, periods=(20, 50, 200)) -> dict[int, pd.Series]:
    return {period: close.rolling(period).mean() for period in periods}

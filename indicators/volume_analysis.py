import pandas as pd


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    average = volume.rolling(period).mean()
    return volume / average.where(average.ne(0))

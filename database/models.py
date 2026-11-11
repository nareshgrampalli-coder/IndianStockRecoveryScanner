from dataclasses import dataclass


@dataclass(frozen=True)
class ScreeningRecord:
    symbol: str
    screened_at_utc: str
    combined_score: float | None
    payload: str

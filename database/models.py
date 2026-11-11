from dataclasses import dataclass


@dataclass(frozen=True)
class ScreeningRecord:
    symbol: str
    screened_at_utc: str
    combined_score: float | None
    payload: str


@dataclass(frozen=True)
class SecurityMapping:
    isin: str
    company_name: str | None
    nse_symbol: str | None
    bse_symbol: str | None


@dataclass(frozen=True)
class PriceBar:
    isin: str
    session_date: str
    provider: str
    retrieved_at_utc: str
    data_quality_score: float
    raw_open: float
    raw_high: float
    raw_low: float
    raw_close: float
    adjusted_open: float
    adjusted_high: float
    adjusted_low: float
    adjusted_close: float
    volume: float | None
    adjustment_factor: float


@dataclass(frozen=True)
class FundamentalObservation:
    isin: str
    financial_period: str | None
    publication_date: str | None
    financial_basis: str
    data_provider: str
    retrieved_at_utc: str
    data_quality_score: float
    payload: str

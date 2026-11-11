from contextlib import closing
import sqlite3
from pathlib import Path

from database.models import FundamentalObservation, PriceBar, ScreeningRecord, SecurityMapping


class ScreeningRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def save(self, records: list[ScreeningRecord]) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS screening_results (
                        symbol TEXT NOT NULL, screened_at_utc TEXT NOT NULL,
                        combined_score REAL, payload TEXT NOT NULL,
                        PRIMARY KEY (symbol, screened_at_utc)
                    )"""
                )
                connection.executemany(
                    """INSERT OR REPLACE INTO screening_results
                       (symbol, screened_at_utc, combined_score, payload) VALUES (?, ?, ?, ?)""",
                    [(r.symbol, r.screened_at_utc, r.combined_score, r.payload) for r in records],
                )

    def save_market_data(
        self,
        securities: list[SecurityMapping],
        prices: list[PriceBar],
        fundamentals: list[FundamentalObservation],
    ) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.executescript(
                    """CREATE TABLE IF NOT EXISTS security_master (
                        isin TEXT PRIMARY KEY, company_name TEXT,
                        nse_symbol TEXT, bse_symbol TEXT, updated_at_utc TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS price_bars (
                        isin TEXT NOT NULL, session_date TEXT NOT NULL, provider TEXT NOT NULL,
                        retrieved_at_utc TEXT NOT NULL, data_quality_score REAL NOT NULL,
                        raw_open REAL NOT NULL, raw_high REAL NOT NULL, raw_low REAL NOT NULL,
                        raw_close REAL NOT NULL, adjusted_open REAL NOT NULL,
                        adjusted_high REAL NOT NULL, adjusted_low REAL NOT NULL,
                        adjusted_close REAL NOT NULL, volume REAL,
                        adjustment_factor REAL NOT NULL,
                        PRIMARY KEY (isin, session_date, provider, retrieved_at_utc)
                    );
                    CREATE TABLE IF NOT EXISTS fundamental_observations (
                        id INTEGER PRIMARY KEY, isin TEXT NOT NULL,
                        financial_period TEXT, publication_date TEXT,
                        financial_basis TEXT NOT NULL, data_provider TEXT NOT NULL,
                        retrieved_at_utc TEXT NOT NULL, data_quality_score REAL NOT NULL,
                        payload TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_fundamentals_isin_publication
                        ON fundamental_observations (isin, publication_date);"""
                )
                connection.executemany(
                    """INSERT INTO security_master
                       (isin, company_name, nse_symbol, bse_symbol, updated_at_utc)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(isin) DO UPDATE SET
                       company_name=excluded.company_name, nse_symbol=excluded.nse_symbol,
                       bse_symbol=excluded.bse_symbol, updated_at_utc=CURRENT_TIMESTAMP""",
                    [(r.isin, r.company_name, r.nse_symbol, r.bse_symbol) for r in securities],
                )
                connection.executemany(
                    """INSERT OR REPLACE INTO price_bars
                       (isin, session_date, provider, retrieved_at_utc, data_quality_score,
                        raw_open, raw_high, raw_low, raw_close, adjusted_open, adjusted_high,
                        adjusted_low, adjusted_close, volume, adjustment_factor)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (r.isin, r.session_date, r.provider, r.retrieved_at_utc,
                         r.data_quality_score, r.raw_open, r.raw_high, r.raw_low,
                         r.raw_close, r.adjusted_open, r.adjusted_high, r.adjusted_low,
                         r.adjusted_close, r.volume, r.adjustment_factor)
                        for r in prices
                    ],
                )
                connection.executemany(
                    """INSERT INTO fundamental_observations
                       (isin, financial_period, publication_date, financial_basis,
                        data_provider, retrieved_at_utc, data_quality_score, payload)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (r.isin, r.financial_period, r.publication_date, r.financial_basis,
                         r.data_provider, r.retrieved_at_utc, r.data_quality_score, r.payload)
                        for r in fundamentals
                    ],
                )

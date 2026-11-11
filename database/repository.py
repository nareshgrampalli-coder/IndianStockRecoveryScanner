from contextlib import closing
import sqlite3
from pathlib import Path

from database.models import ScreeningRecord


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

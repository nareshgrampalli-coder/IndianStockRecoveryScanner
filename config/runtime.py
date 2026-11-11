from pathlib import Path

DEFAULTS = {
    "universe_url": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "request_timeout_seconds": 30,
    "technical_workers": 5,
    "history_period": "1y",
    "ingestion_history_period": "5y",
    "database_path": "data/screening.sqlite3",
    "security_master_path": "config/stock_universe.csv",
}


def load_settings(path: str | Path) -> dict:
    settings = DEFAULTS.copy()
    path = Path(path)
    if not path.exists():
        return settings
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip().strip("\"'") for part in line.split(":", 1))
        if key in settings:
            settings[key] = type(settings[key])(value)
    return settings

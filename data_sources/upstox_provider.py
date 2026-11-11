"""Upstox provider boundary; credentials and instrument keys are required."""


class UpstoxProvider:
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token

    def history(self, instrument_key: str, start: str, end: str):
        raise NotImplementedError(
            "Upstox history is not configured. Supply an access token and instrument key."
        )

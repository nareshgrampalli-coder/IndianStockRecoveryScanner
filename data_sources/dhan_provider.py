"""Dhan provider boundary; credentials and API configuration are required."""


class DhanProvider:
    def __init__(self, client_id: str | None = None, access_token: str | None = None):
        self.client_id = client_id
        self.access_token = access_token

    def history(self, symbol: str, start: str, end: str):
        raise NotImplementedError(
            "Dhan history is not configured. Supply Dhan API credentials and instrument identifiers."
        )

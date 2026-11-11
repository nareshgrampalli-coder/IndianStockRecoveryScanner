"""BSE provider boundary for official exchange disclosures."""


class BSEProvider:
    def filings(self, symbol: str):
        raise NotImplementedError(
            "BSE filing retrieval is not configured. Use official BSE disclosure downloads."
        )

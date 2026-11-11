import unittest
import warnings
from unittest.mock import Mock, patch

import pandas as pd

from data_sources.nse_provider import NSEProvider


class NSEProviderTests(unittest.TestCase):
    def test_constituent_cleanup_warns_and_drops_invalid_rows(self):
        response = Mock()
        response.content = (
            b"Symbol,Company Name,ISIN Code\n"
            b"ABC,ABC Limited,INE000A01000\n"
            b"DUMMY,Placeholder,DUM545A01024\n"
            b",Missing Symbol,INE000B01000\n"
            b"ABC,ABC Limited,INE000A01000\n"
        )
        response.raise_for_status.return_value = None

        with patch("data_sources.nse_provider.requests.get", return_value=response):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                universe = NSEProvider("https://example.test/universe.csv").nifty500()

        self.assertEqual(universe["symbol"].tolist(), ["ABC"])
        self.assertEqual(universe["isin"].tolist(), ["INE000A01000"])
        messages = [str(warning.message) for warning in caught]
        self.assertTrue(any("invalid ISIN" in message for message in messages))
        self.assertTrue(any("incomplete" in message for message in messages))
        self.assertTrue(any("duplicate" in message for message in messages))

    def test_constituent_cleanup_rejects_conflicting_canonical_mappings(self):
        response = Mock()
        response.content = (
            b"Symbol,Company Name,ISIN Code\n"
            b"ABC,ABC Limited,INE000A01000\n"
            b"ABC,ABC Limited,INE000B01000\n"
        )
        response.raise_for_status.return_value = None

        with patch("data_sources.nse_provider.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "symbols mapped to multiple ISINs"):
                NSEProvider("https://example.test/universe.csv").nifty500()


if __name__ == "__main__":
    unittest.main()

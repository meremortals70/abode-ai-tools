"""Config-flow data handling tests."""

from __future__ import annotations

import unittest

from tests import fake_ha

from abode_ai_tools import config_flow  # noqa: E402 - fake_ha sets sys.path

URL = "paperless_url"
TOKEN = "paperless_token"


class ConfigDataTests(unittest.TestCase):
    def test_clean_drops_blanks(self) -> None:
        self.assertEqual(
            config_flow._clean({URL: "http://x", TOKEN: "", "other": None}),
            {URL: "http://x"},
        )

    def test_merge_keeps_existing_token_when_blank(self) -> None:
        existing = {URL: "http://old", TOKEN: "old-token"}
        merged = config_flow._merge(
            existing, {URL: "http://new", TOKEN: ""}
        )
        self.assertEqual(merged[URL], "http://new")
        self.assertEqual(merged[TOKEN], "old-token")

    def test_merge_replaces_token_when_supplied(self) -> None:
        existing = {URL: "http://old", TOKEN: "old-token"}
        merged = config_flow._merge(
            existing, {URL: "http://new", TOKEN: "new-token"}
        )
        self.assertEqual(merged[TOKEN], "new-token")

    def test_merge_clearing_url_clears_token(self) -> None:
        existing = {URL: "http://old", TOKEN: "old-token"}
        merged = config_flow._merge(existing, {URL: "", TOKEN: ""})
        self.assertEqual(merged, {})

    def test_merge_preserves_other_keys(self) -> None:
        existing = {URL: "http://old", TOKEN: "old-token", "other": "keep"}
        merged = config_flow._merge(existing, {URL: "http://new"})
        self.assertEqual(merged["other"], "keep")


if __name__ == "__main__":
    unittest.main()

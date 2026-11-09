"""Tests for the pure bounding and URL helpers.

Run with: python -m unittest discover -s tests -v
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(
    0,
    str(
        pathlib.Path(__file__).parents[1]
        / "custom_components"
        / "abode_ai_tools"
    ),
)

import util  # noqa: E402 - path is set above


class ShortTests(unittest.TestCase):
    """Every string exposed to the model goes through this helper."""

    def test_short_string_is_unchanged(self) -> None:
        self.assertEqual(util.short("kitchen light", 80), "kitchen light")

    def test_long_string_is_capped(self) -> None:
        result = util.short("x" * 100, 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("..."))

    def test_non_string_is_converted(self) -> None:
        self.assertEqual(util.short(123, 10), "123")
        self.assertEqual(util.short(None, 10), "None")

    def test_tiny_limit_has_no_room_for_ellipsis(self) -> None:
        self.assertEqual(util.short("abcdef", 3), "abc")


class BoundJsonTests(unittest.TestCase):
    """Paperless custom fields are arbitrary JSON and need recursion."""

    def test_nested_strings_are_capped(self) -> None:
        value = {
            "a": "x" * 50,
            "b": [1, "y" * 50],
            "c": {"d": "z" * 50},
        }
        result = util.bound_json(value, 10)
        self.assertEqual(len(result["a"]), 10)
        self.assertEqual(len(result["b"][1]), 10)
        self.assertEqual(len(result["c"]["d"]), 10)

    def test_scalars_keep_their_type(self) -> None:
        self.assertEqual(util.bound_json(5, 10), 5)
        self.assertIs(util.bound_json(True, 10), True)
        self.assertIsNone(util.bound_json(None, 10))

    def test_list_length_is_capped(self) -> None:
        self.assertEqual(len(util.bound_json(list(range(50)), 10)), 10)


class SafeUrlTests(unittest.TestCase):
    """Logs must never contain userinfo, a path or a query token."""

    def test_userinfo_and_query_are_removed(self) -> None:
        self.assertEqual(
            util.safe_url("https://user:pass@example.com:8443/mcp?token=abc"),
            "https://example.com:8443",
        )

    def test_plain_url_keeps_scheme_and_host(self) -> None:
        self.assertEqual(
            util.safe_url("http://paperless.local/mcp"),
            "http://paperless.local",
        )

    def test_invalid_port_does_not_raise(self) -> None:
        self.assertEqual(
            util.safe_url("https://example.com:notaport/mcp"),
            "https://example.com",
        )


if __name__ == "__main__":
    unittest.main()

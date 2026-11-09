"""Behaviour and hardening tests for the Paperless proxy."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

from tests import fake_ha

from abode_ai_tools import paperless  # noqa: E402 - fake_ha sets sys.path

URL = "http://paperless.local/mcp"


class RaisingSession:
    def post(self, url: str, **kwargs):
        raise TimeoutError


class PaperlessRpcTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        paperless._FAILURES.clear()
        self.hass = fake_ha.build_hass()

    def tearDown(self) -> None:
        paperless._FAILURES.clear()
        fake_ha.SESSION = None

    def _response(
        self,
        text: str | bytes = "",
        *,
        status: int = 200,
        content_type: str = "application/json",
        content_length: int | None = None,
    ) -> fake_ha.FakeResponse:
        body = text.encode() if isinstance(text, str) else text
        return fake_ha.FakeResponse(
            body,
            status=status,
            content_type=content_type,
            content_length=content_length,
        )

    def _rpc_text(self, text: str) -> str:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": text}]
                },
            }
        )

    async def test_json_text_block_is_decoded(self) -> None:
        inner = json.dumps({"results": [{"id": 1}]})
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(self._rpc_text(inner))
        )
        result = await paperless._rpc(
            self.hass, URL, None, "query_documents", {}
        )
        self.assertEqual(result, {"results": [{"id": 1}]})

    async def test_plain_text_block_is_returned(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(self._rpc_text("hello"))
        )
        result = await paperless._rpc(
            self.hass, URL, None, "query_documents", {}
        )
        self.assertEqual(result, "hello")

    async def test_sse_response_is_decoded(self) -> None:
        inner = json.dumps({"results": []})
        body = f"data: {self._rpc_text(inner)}\n\n"
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(body, content_type="text/event-stream")
        )
        result = await paperless._rpc(
            self.hass, URL, None, "query_documents", {}
        )
        self.assertEqual(result, {"results": []})

    async def test_error_string_is_reported_not_crashed(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(
                json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "error": "bad"}
                )
            )
        )
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("bad", str(exc.exception))

    async def test_error_object_is_reported(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "error": {"message": "bad"},
                    }
                )
            )
        )
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("bad", str(exc.exception))

    async def test_non_dict_message_is_reported(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(self._response("[]"))
        with self.assertRaises(paperless.PaperlessError):
            await paperless._rpc(self.hass, URL, None, "query_documents", {})

    async def test_non_dict_result_is_reported(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(json.dumps({"result": []}))
        )
        with self.assertRaises(paperless.PaperlessError):
            await paperless._rpc(self.hass, URL, None, "query_documents", {})

    async def test_missing_content_is_reported(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(json.dumps({"result": {}}))
        )
        with self.assertRaises(paperless.PaperlessError):
            await paperless._rpc(self.hass, URL, None, "query_documents", {})

    async def test_non_dict_content_block_is_skipped(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(
                json.dumps(
                    {
                        "result": {
                            "content": [1, {"type": "text", "text": "ok"}]
                        }
                    }
                )
            )
        )
        result = await paperless._rpc(
            self.hass, URL, None, "query_documents", {}
        )
        self.assertEqual(result, "ok")

    async def test_content_length_cap(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response("", content_length=paperless.MAX_RESPONSE_BYTES + 1)
        )
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("too large", str(exc.exception))

    async def test_body_cap(self) -> None:
        fake_ha.SESSION = fake_ha.FakeSession(self._response(b"x" * 11))
        with patch.object(paperless, "MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(paperless.PaperlessError) as exc:
                await paperless._rpc(
                    self.hass, URL, None, "query_documents", {}
                )
        self.assertIn("too large", str(exc.exception))

    async def test_redirects_are_not_followed(self) -> None:
        session = fake_ha.FakeSession(self._response("", status=302))
        fake_ha.SESSION = session
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("HTTP 302", str(exc.exception))
        self.assertIs(session.last_request["allow_redirects"], False)

    async def test_timeout_opens_breaker(self) -> None:
        fake_ha.SESSION = RaisingSession()
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("timed out", str(exc.exception))
        self.assertTrue(paperless.breaker_is_open(URL))

    async def test_success_closes_breaker(self) -> None:
        paperless.record_failure(URL, now=0)
        self.assertTrue(paperless.breaker_is_open(URL, now=0))
        fake_ha.SESSION = fake_ha.FakeSession(
            self._response(self._rpc_text("ok"))
        )
        await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertFalse(paperless.breaker_is_open(URL))

    async def test_open_breaker_fails_before_request(self) -> None:
        paperless.record_failure(URL)
        session = fake_ha.FakeSession(self._response(self._rpc_text("ok")))
        fake_ha.SESSION = session
        with self.assertRaises(paperless.PaperlessError) as exc:
            await paperless._rpc(self.hass, URL, None, "query_documents", {})
        self.assertIn("temporarily unavailable", str(exc.exception))
        self.assertEqual(session.last_request, {})


class PaperlessProjectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        paperless._FAILURES.clear()
        self.hass = fake_ha.build_hass()

    async def test_doc_record_caps_strings_and_keeps_date(self) -> None:
        doc = {
            "id": 1,
            "title": "T" * 500,
            "created_date": "2026-11-09T10:00:00",
            "correspondent": {"name": "C" * 200},
            "document_type": {"name": "D" * 200},
            "__search_hit__": {
                "highlights": "<span>hello</span> " + "x" * 500
            },
        }
        record = paperless._doc_record(doc, with_excerpt=True)
        self.assertLessEqual(len(record["title"]), paperless.MAX_TITLE_CHARS)
        self.assertEqual(record["filed"], "2026-11-09")
        self.assertLessEqual(
            len(record["correspondent"]), paperless.MAX_METADATA_CHARS
        )
        self.assertLessEqual(
            len(record["document_type"]), paperless.MAX_METADATA_CHARS
        )
        self.assertLessEqual(len(record["excerpt"]), paperless.MAX_EXCERPT_CHARS)

    async def test_excerpt_handles_non_dict_search_hit(self) -> None:
        self.assertEqual(
            paperless._excerpt({"__search_hit__": "not a dict"}), ""
        )

    async def test_find_document_filters_non_dict_results(self) -> None:
        tool = paperless.FindDocumentTool(URL, None)
        with patch.object(
            paperless,
            "_rpc",
            new=AsyncMock(
                return_value={"results": [None, {"id": 1, "title": "ok"}]}
            ),
        ):
            result = await tool.async_call(
                self.hass,
                fake_ha.make_input("find_document", {"query": "ok"}),
                fake_ha.make_context(),
            )
        self.assertEqual(result.data["count"], 1)
        self.assertEqual(len(result.data["results"]), 1)
        self.assertEqual(result.data["results"][0]["id"], 1)

    async def test_get_document_caps_tags_and_custom_fields(self) -> None:
        tool = paperless.GetDocumentTool(URL, None)
        with patch.object(
            paperless,
            "_rpc",
            new=AsyncMock(
                return_value={
                    "id": 1,
                    "title": "doc",
                    "tags": [{"name": "T" * 200}],
                    "custom_fields": [
                        {"field": 1, "value": "V" * 500},
                        {"nested": {"deep": "D" * 500}},
                    ],
                }
            ),
        ):
            result = await tool.async_call(
                self.hass,
                fake_ha.make_input("get_document", {"id": 1}),
                fake_ha.make_context(),
            )
        self.assertLessEqual(
            len(result.data["tags"][0]), paperless.MAX_TAG_CHARS
        )
        self.assertLessEqual(
            len(result.data["custom_fields"][0]["value"]),
            paperless.MAX_CUSTOM_FIELD_CHARS,
        )
        self.assertLessEqual(
            len(result.data["custom_fields"][1]["nested"]["deep"]),
            paperless.MAX_CUSTOM_FIELD_CHARS,
        )

    async def test_read_document_handles_none_and_caps_text(self) -> None:
        tool = paperless.ReadDocumentTool(URL, None)
        with patch.object(paperless, "_rpc", new=AsyncMock(return_value=None)):
            missing = await tool.async_call(
                self.hass,
                fake_ha.make_input("read_document", {"id": 9}),
                fake_ha.make_context(),
            )
        self.assertTrue(missing.error)

        with patch.object(
            paperless,
            "_rpc",
            new=AsyncMock(return_value={"content": "x" * 5000}),
        ):
            result = await tool.async_call(
                self.hass,
                fake_ha.make_input("read_document", {"id": 1}),
                fake_ha.make_context(),
            )
        self.assertEqual(
            len(result.data["content"]), paperless.MAX_CONTENT_CHARS
        )
        self.assertTrue(result.data["truncated"])


if __name__ == "__main__":
    unittest.main()

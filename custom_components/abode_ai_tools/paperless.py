"""Abode AI Tools — Paperless-ngx document retrieval, bounded for the voice path.

WHY THIS EXISTS

Paperless-ngx is a system of truth. The house needs to READ it by voice
("how much warranty is left on the brushcutter"), never to write to it.

The obvious route — attaching baruchiro/paperless-mcp to the conversation
agent via Home Assistant's `mcp` integration — does not work here for two
reasons, both read from that project's source on 28 Jul 2026:

  * It registers 44 tools (documents 10, mail 8, correspondents 6,
    customFields 6, documentTypes 6, tags 5, notes 3) and ships no read-only
    flag and no tool-selection option: server.ts calls all seven register*Tools
    unconditionally, and grep for readonly/read_only/disable/filter across
    index.ts, server.ts, package.json and Dockerfile returns nothing.
    Home Assistant's MCP client has no per-tool selection either, so every
    voice turn — including "turn on the hallway light" — would carry all 44
    schemas, plus post_document, delete_pages and bulk_edit_documents.
  * Results are unbounded. A single document's text can exceed the whole
    prompt budget.

This module exposes exactly THREE tools, each a thin proxy to one MCP tool,
with the result projected down to a fixed field list and hard-capped. Same
discipline as _record() in __init__.py, for the same reason.

WRITE PROTECTION IS THE CREDENTIAL, NOT THIS FILE

Restricting the tool list here stops the MODEL reaching a write tool. It does
not stop anything else that can reach the MCP endpoint. The only real control
is the Paperless-ngx API token the container runs with: issue it to a
view-only user and delete_tag / post_document / bulk_edit_documents fail at
Paperless regardless of what calls them.

Note also that paperless-mcp's getBearerToken() falls back to the container's
--token when a request carries no Authorization header, so the endpoint is
effectively anonymous. Restrict it at Caddy.

TRANSPORT

paperless-mcp --http serves stateless Streamable HTTP: sessionIdGenerator is
undefined and a fresh server+transport is built per request (index.ts:105).
POST only; GET /mcp returns 405. So this module speaks plain JSON-RPC over
one aiohttp POST per call — no MCP SDK, no session handling, and
manifest.json keeps "requirements": [].

UNVERIFIED — TEST BEFORE TRUSTING

Whether a bare tools/call POST is accepted without a preceding `initialize`
is NOT established. The stateless design implies it must be, since no state
survives between requests, but that is inference, not evidence. Prove it with
the curl in the deployment notes before wiring this into a pipeline. If it is
rejected, _rpc() gains an initialize POST and nothing else changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard limits. Every one bounds a number Paperless leaves unbounded. Changing
# them changes the measured latency of any turn that touches a document, so
# change them deliberately and re-measure.
# ---------------------------------------------------------------------------

MAX_DOCUMENTS = 8
"""Maximum documents returned by find_document, ever."""

MAX_EXCERPT_CHARS = 400
"""Maximum characters of search highlight returned per document.

8 documents x 400 chars is ~800 tokens worst case, and usually far less.
"""

MAX_CONTENT_CHARS = 4000
"""Maximum characters of document text returned by read_document.

At roughly 4 characters per token this is ~1,000 tokens of prefill, which at
337 tok/s (252 as-built §6.14) costs ~3 s before the model can speak. It is
already the most expensive thing in this file. Do not raise it without
measuring the turn.
"""

RPC_TIMEOUT = 20
"""Seconds. Paperless full-text search on a large archive is not instant."""

_ACCEPT = "application/json, text/event-stream"


class PaperlessError(Exception):
    """Raised when the MCP server cannot be reached or returns an error."""


async def _rpc(
    hass: HomeAssistant, url: str, token: str | None, tool: str, arguments: dict
) -> Any:
    """Call one MCP tool and return its decoded payload.

    Returns whatever the tool put in its text content block, JSON-decoded when
    it parses as JSON and the raw string when it does not.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {"Content-Type": "application/json", "Accept": _ACCEPT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(RPC_TIMEOUT):
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise PaperlessError(f"HTTP {resp.status}")
                body = await resp.text()
                content_type = resp.headers.get("Content-Type", "")
    except TimeoutError as err:
        raise PaperlessError("timed out") from err
    except PaperlessError:
        raise
    except Exception as err:  # noqa: BLE001 - never raise into the turn
        raise PaperlessError(str(err)) from err

    # The transport may answer as JSON or as a single SSE event, depending on
    # what the SDK negotiates from the Accept header. Handle both.
    if "text/event-stream" in content_type:
        data_lines = [
            line[5:].strip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise PaperlessError("empty event stream")
        body = data_lines[-1]

    try:
        message = json.loads(body)
    except ValueError as err:
        raise PaperlessError("unparseable response") from err

    if "error" in message:
        raise PaperlessError(str(message["error"].get("message", "rpc error")))

    result = message.get("result") or {}
    if result.get("isError"):
        raise PaperlessError("tool reported an error")

    for block in result.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            try:
                return json.loads(block["text"])
            except ValueError:
                return block["text"]

    raise PaperlessError("no content in tool result")


def _name_of(value: Any) -> str:
    """Paperless returns correspondent/document_type as {id, name} objects."""
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if value is None:
        return ""
    return str(value)


_TAG_RE = re.compile(r"<[^>]+>")


def _excerpt(doc: dict) -> str:
    """Return the search highlight, HTML stripped and capped.

    query_documents embeds the matching passage in __search_hit__.highlights,
    wrapped in <span class="match ..."> markers. It is worth returning because
    it often lets the model judge whether a hit is the right document without
    a second round trip - and decode, not prefill, is this hardware's binding
    constraint (abode_ai_tools as-built, Q19).

    It is NOT a substitute for read_document when the answer involves a date.
    The only trustworthy dates are inside the document text; see _doc_record.
    """
    hit = doc.get("__search_hit__") or {}
    raw = hit.get("highlights") or ""
    text = _TAG_RE.sub("", str(raw)).replace("\n", " ")
    text = " ".join(text.split())
    return text[:MAX_EXCERPT_CHARS]


def _doc_record(doc: dict, *, with_excerpt: bool = False) -> dict[str, Any]:
    """Return the ONLY shape a document search result ever takes."""
    record: dict[str, Any] = {
        "id": doc.get("id"),
        "title": doc.get("title") or "",
        # NOT the date on the document. Paperless "created" is when the
        # document entered the archive (architect, 28 Jul 2026). A date that
        # matters - invoice date, purchase date, expiry - is only in the
        # document text. Named to make that impossible to misread.
        "filed": (doc.get("created_date") or doc.get("created") or "")[:10],
        "correspondent": _name_of(doc.get("correspondent")),
        "document_type": _name_of(doc.get("document_type")),
    }
    if with_excerpt:
        excerpt = _excerpt(doc)
        if excerpt:
            record["excerpt"] = excerpt
    return record


def _results_of(payload: Any) -> list[dict]:
    """Pull the document list out of whatever shape the tool returned."""
    if isinstance(payload, dict):
        for key in ("results", "documents", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
    if isinstance(payload, list):
        return payload
    return []


class _PaperlessTool(llm.Tool):
    """Base for the three tools. Holds the endpoint from configuration."""

    # All three tools only read. The integration must be declared explicitly
    # since HA 2026.10; see the note on SearchEntitiesTool in __init__.py.
    integration = DOMAIN
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )

    def __init__(self, url: str, token: str | None) -> None:
        """Store the MCP endpoint this tool proxies to."""
        self._url = url
        self._token = token


class FindDocumentTool(_PaperlessTool):
    """Full-text search across the document archive."""

    name = "find_document"
    title = "Find document"
    description = (
        "Search the household document archive by text. Use for questions "
        "about receipts, warranties, manuals, bills, insurance or contracts. "
        "Returns at most 8 documents with their id, title, and the matching "
        "passage. 'filed' is the date the document was added to the archive, "
        "NOT the date printed on it - never use it as an invoice, purchase or "
        "expiry date. For any question involving a date, call read_document "
        "and read the date from the document text."
    )
    parameters = vol.Schema({vol.Required("query"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Search documents, capped and projected."""
        query = str(tool_input.tool_args["query"]).strip()
        if not query:
            return llm.ToolResult(data={"error": "query is required."}, error=True)

        try:
            payload = await _rpc(
                hass,
                self._url,
                self._token,
                # query_documents, NOT search_documents: the latter's own
                # description marks it a deprecated compatibility wrapper.
                "query_documents",
                {"query": query, "page_size": MAX_DOCUMENTS},
            )
        except PaperlessError as err:
            _LOGGER.warning("abode_ai_tools: paperless search failed: %s", err)
            return llm.ToolResult(
                data={"error": "The document archive is not reachable."},
                error=True,
            )

        documents = _results_of(payload)
        records = [
            _doc_record(doc, with_excerpt=True)
            for doc in documents[:MAX_DOCUMENTS]
        ]
        total = payload.get("count") if isinstance(payload, dict) else None
        if not isinstance(total, int):
            total = len(documents)
        result: dict[str, Any] = {"results": records, "count": total}
        if total > len(records):
            result["note"] = (
                f"INCOMPLETE: only {len(records)} of {total} shown. "
                "Narrow the query and call again."
            )
        return llm.ToolResult(data=result)


class GetDocumentTool(_PaperlessTool):
    """Metadata for one document, including custom fields."""

    name = "get_document"
    title = "Get document details"
    description = (
        "Get the details of one document by id: title, correspondent, type, "
        "tags and custom fields. 'filed' is when it entered the archive, not "
        "the date on the document. Use read_document for its text."
    )
    parameters = vol.Schema({vol.Required("id"): int})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Return one document's projected metadata."""
        doc_id = tool_input.tool_args["id"]
        try:
            payload = await _rpc(
                hass, self._url, self._token, "get_document", {"id": doc_id}
            )
        except PaperlessError as err:
            _LOGGER.warning("abode_ai_tools: paperless get %s failed: %s", doc_id, err)
            return llm.ToolResult(
                data={"error": "The document archive is not reachable."},
                error=True,
            )

        if not isinstance(payload, dict):
            return llm.ToolResult(
                data={"error": f"Document {doc_id} was not found."}, error=True
            )

        record = _doc_record(payload)
        record["tags"] = [
            _name_of(tag) for tag in (payload.get("tags") or [])[:10]
        ]
        custom = payload.get("custom_fields") or []
        record["custom_fields"] = custom[:10] if isinstance(custom, list) else []
        return llm.ToolResult(data=record)


class ReadDocumentTool(_PaperlessTool):
    """The text of one document, hard-truncated."""

    name = "read_document"
    title = "Read document"
    description = (
        "Read the text of one document by id. Call find_document first to get "
        "the id. Long documents are truncated."
    )
    parameters = vol.Schema({vol.Required("id"): int})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Return the document text, capped at MAX_CONTENT_CHARS."""
        doc_id = tool_input.tool_args["id"]
        try:
            payload = await _rpc(
                hass,
                self._url,
                self._token,
                "get_document_content",
                {"id": doc_id},
            )
        except PaperlessError as err:
            _LOGGER.warning("abode_ai_tools: paperless read %s failed: %s", doc_id, err)
            return llm.ToolResult(
                data={"error": "The document archive is not reachable."},
                error=True,
            )

        if isinstance(payload, dict):
            text = payload.get("content") or payload.get("text") or ""
        else:
            text = str(payload)

        truncated = len(text) > MAX_CONTENT_CHARS
        return llm.ToolResult(
            data={
                "id": doc_id,
                "content": text[:MAX_CONTENT_CHARS],
                "truncated": truncated,
            }
        )


def build_tools(url: str, token: str | None) -> list[llm.Tool]:
    """Return the three Paperless tools bound to this endpoint."""
    return [
        FindDocumentTool(url, token),
        GetDocumentTool(url, token),
        ReadDocumentTool(url, token),
    ]

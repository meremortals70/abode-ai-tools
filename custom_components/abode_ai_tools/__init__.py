"""Abode AI Tools — a bounded LLM tool API for the voice path.

WHY THIS EXISTS

The ha-mcp add-on returns full entity records. One `ha_search` call measured
1,904 tokens, which at this hardware's prefill rate of 342.92 tok/s costs 6.2 s
on every turn, because the model must read the tool result before it can speak.
ha-mcp's add-on config (7.14.2) exposes no option for result projection or
response size — only `tool_search_max_results`, `pinned_tools`, `disabled_tools`
— so its output cannot be bounded by configuration.

This component registers its own Home Assistant LLM API with four tools whose
schemas and result shapes are fixed in code. Both costs become deterministic:

  * Tool schemas are small, so the cached prompt prefix is small.
  * Every result is hard-capped by MAX_RESULTS and a fixed field list, so no
    tool call can return an unbounded payload.

It replaces ha-mcp ON THE VOICE PATH ONLY. ha-mcp remains available for
administrative and build-time use through its own MCP endpoint.

DATETIME

One tool is named `GetDateTime`. Home Assistant appends a timestamp with
SECONDS resolution to the conversation system prompt unless an exposed tool's
name ends in "GetDateTime" (chat_log.py:738-749, 2026.7.4). That timestamp
changes every second, so the prompt prefix never repeats and the llama.cpp KV
cache can never match it. With this tool present the prefix is byte-stable.

This makes the separate `abode_clock` component redundant. Leaving it installed
is harmless — when more than one LLM API is selected, HA wraps tools in
NamespacedTool, which PREPENDS "<namespace>__" (llm.py:373), so both names still
end in "GetDateTime".

EXPOSURE

Only entities exposed to the conversation assistant are visible, via
homeassistant.components.homeassistant.exposed_entities.async_should_expose
(exposed_entities.py:515). Control what the house can do from
Settings -> Voice assistants -> Expose, not by editing this file.

INSTALL

  1. Copy this directory to /config/custom_components/abode_ai_tools/
  2. Add the integration via Settings -> Devices & Services
  3. ha core check && ha core stop && ha core start
  4. Settings -> Devices & services -> your conversation agent -> Configure
     Tool Providers: tick "Abode AI Tools", untick "ha-mcp"
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components.homeassistant.exposed_entities import (
    async_should_expose,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util

from . import paperless
from .const import CONF_PAPERLESS_TOKEN, CONF_PAPERLESS_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONVERSATION_DOMAIN = "conversation"

type AbodeAIToolsEntry = ConfigEntry[Callable[[], None]]
"""The config entry's runtime_data is the llm API's unregister callable."""


# ---------------------------------------------------------------------------
# Hard limits. These are the whole point of this component. Every one of them
# bounds a number that was previously unbounded. Changing them changes the
# measured latency of every turn, so change them deliberately and re-measure.
# ---------------------------------------------------------------------------

MAX_RESULTS = 20
"""Maximum entity records returned by search_entities, ever."""

MAX_ATTRIBUTES = 6
"""Maximum attributes returned by get_entity_state."""

CONTROLLABLE_DOMAINS = (
    "light",
    "switch",
    "fan",
    "cover",
    "climate",
    "media_player",
    "lock",
    "vacuum",
    "scene",
    "script",
    "humidifier",
    "water_heater",
    "valve",
    "input_boolean",
    "button",
)

READABLE_DOMAINS = CONTROLLABLE_DOMAINS + (
    "sensor",
    "binary_sensor",
    "person",
    "device_tracker",
    "weather",
    "calendar",
    "sun",
)

ALLOWED_SERVICE_DOMAINS = set(CONTROLLABLE_DOMAINS) | {"homeassistant"}
"""A service call outside these domains is refused. Keeps the model away from
automation editing, backups, recorder purges and anything else destructive."""


def _area_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return the area name for an entity, or an empty string."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return ""

    area_id = entry.area_id
    if area_id is None and entry.device_id:
        device = dr.async_get(hass).async_get(entry.device_id)
        area_id = device.area_id if device else None

    if area_id is None:
        return ""

    area = ar.async_get(hass).async_get_area(area_id)
    return area.name if area else ""


def _visible(hass: HomeAssistant, entity_id: str) -> bool:
    """Return True if this entity is exposed to the conversation assistant."""
    try:
        return async_should_expose(hass, CONVERSATION_DOMAIN, entity_id)
    except Exception:  # noqa: BLE001 - never let exposure lookup break a turn
        _LOGGER.debug("abode_ai_tools: exposure check failed for %s", entity_id)
        return False


def _record(hass: HomeAssistant, entity_id: str) -> dict[str, str]:
    """Return the ONLY shape a search result ever takes. Four short fields."""
    state = hass.states.get(entity_id)
    return {
        "entity_id": entity_id,
        "name": (state.attributes.get("friendly_name") if state else None)
        or entity_id,
        "area": _area_name(hass, entity_id),
        "state": state.state if state else "unknown",
    }


class SearchEntitiesTool(llm.Tool):
    """Find entities by name, area or domain. Results are capped in code."""

    name = "search_entities"
    description = (
        "Find devices in this home. Returns at most 20 matches, each with its "
        "entity_id, name, area and current state. Use before calling "
        "call_service when you do not already know the entity_id."
    )
    parameters = vol.Schema(
        {
            vol.Optional("query"): str,
            vol.Optional("domain"): str,
            vol.Optional("area"): str,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Search the entity registry and return capped, projected records."""
        args = tool_input.tool_args
        query = (args.get("query") or "").strip().lower()
        domain = (args.get("domain") or "").strip().lower()
        area = (args.get("area") or "").strip().lower()

        matches: list[dict[str, str]] = []
        truncated = False

        for entity_id in hass.states.async_entity_ids():
            if entity_id.split(".")[0] not in READABLE_DOMAINS:
                continue
            if domain and not entity_id.startswith(f"{domain}."):
                continue
            if not _visible(hass, entity_id):
                continue

            record = _record(hass, entity_id)

            if area and area not in record["area"].lower():
                continue
            if query and (
                query not in record["name"].lower()
                and query not in entity_id.lower()
            ):
                continue

            if len(matches) >= MAX_RESULTS:
                truncated = True
                break
            matches.append(record)

        result: dict[str, Any] = {"results": matches, "count": len(matches)}
        if truncated:
            result["note"] = (
                f"More than {MAX_RESULTS} matches. Narrow with domain or area."
            )
        return result


class GetEntityStateTool(llm.Tool):
    """Read one entity's state and a bounded set of its attributes."""

    name = "get_entity_state"
    description = (
        "Get the current state of one entity by entity_id, with a few of its "
        "most useful attributes."
    )
    parameters = vol.Schema({vol.Required("entity_id"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Return one entity's state, with attributes capped."""
        entity_id = tool_input.tool_args["entity_id"]

        if not _visible(hass, entity_id):
            return {"error": f"{entity_id} is not available."}

        state = hass.states.get(entity_id)
        if state is None:
            return {"error": f"{entity_id} does not exist."}

        skip = {"friendly_name", "icon", "supported_features", "device_class"}
        attributes = {
            key: value
            for key, value in list(state.attributes.items())
            if key not in skip
        }
        trimmed = dict(list(attributes.items())[:MAX_ATTRIBUTES])

        return {
            "entity_id": entity_id,
            "name": state.attributes.get("friendly_name", entity_id),
            "area": _area_name(hass, entity_id),
            "state": state.state,
            "attributes": trimmed,
        }


class CallServiceTool(llm.Tool):
    """Act on a device. Domain-restricted, single entity, fixed reply."""

    name = "call_service"
    description = (
        "Act on a device. service is like 'light.turn_on' or 'cover.close_cover'. "
        "entity_id must be an exact entity_id from search_entities."
    )
    parameters = vol.Schema(
        {
            vol.Required("service"): str,
            vol.Required("entity_id"): str,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Call a service against one exposed entity."""
        args = tool_input.tool_args
        service = str(args["service"]).strip()
        entity_id = str(args["entity_id"]).strip()

        if "." not in service:
            return {"error": "service must look like 'light.turn_on'."}

        domain, name = service.split(".", 1)

        if domain not in ALLOWED_SERVICE_DOMAINS:
            return {"error": f"{domain} services are not permitted."}
        if not hass.services.has_service(domain, name):
            return {"error": f"{service} does not exist."}
        if not _visible(hass, entity_id):
            return {"error": f"{entity_id} is not available."}

        try:
            await hass.services.async_call(
                domain,
                name,
                {"entity_id": entity_id},
                blocking=True,
                context=llm_context.context,
            )
        except Exception as err:  # noqa: BLE001 - report, never raise into the turn
            _LOGGER.warning("abode_ai_tools: %s on %s failed: %s", service, entity_id, err)
            return {"error": f"{service} failed."}

        return {"success": True}


class GetDateTimeTool(llm.Tool):
    """Return the current local date and time on request."""

    name = "GetDateTime"
    description = (
        "Get the current local date and time. Call this only when the user asks "
        "about the date, the time, or the day of the week."
    )
    parameters = vol.Schema({})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Return the current date and time."""
        now = dt_util.now()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
        }


class AbodeAIToolsAPI(llm.API):
    """The bounded tool surface offered to the conversation agent."""

    def __init__(
        self,
        *args: Any,
        extra_tools: list[llm.Tool] | None = None,
        **kwargs: Any,
    ) -> None:
        """Store any optional tools alongside the four fixed ones."""
        super().__init__(*args, **kwargs)
        self._extra_tools = extra_tools or []

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the API instance with its fixed tools plus any extras."""
        prompt = (
            "You control this home. Use search_entities to find a device, "
            "then call_service to act on it. Use get_entity_state to read "
            "one device. Never guess an entity_id."
        )
        if self._extra_tools:
            prompt += (
                " For questions about receipts, warranties, manuals, bills or "
                "contracts, use find_document then read_document."
            )
        return llm.APIInstance(
            api=self,
            api_prompt=prompt,
            llm_context=llm_context,
            tools=[
                SearchEntitiesTool(),
                GetEntityStateTool(),
                CallServiceTool(),
                GetDateTimeTool(),
                *self._extra_tools,
            ],
        )


async def async_setup_entry(hass: HomeAssistant, entry: AbodeAIToolsEntry) -> bool:
    """Register the Abode AI Tools LLM API for this config entry."""
    url: str | None = entry.data.get(CONF_PAPERLESS_URL)
    token: str | None = entry.data.get(CONF_PAPERLESS_TOKEN)

    extra_tools: list[llm.Tool] = []
    if url:
        extra_tools = paperless.build_tools(url, token)
        _LOGGER.info("abode_ai_tools: paperless tools enabled (%s)", url)
    else:
        _LOGGER.info("abode_ai_tools: paperless not configured, four tools only")

    # async_register_api returns the unregister callable and raises
    # HomeAssistantError if the id is already registered
    # (homeassistant/helpers/llm.py, async_register_api). Holding the
    # callable on runtime_data is what makes reload work.
    entry.runtime_data = llm.async_register_api(
        hass,
        AbodeAIToolsAPI(
            hass=hass,
            id=DOMAIN,
            name="Abode AI Tools",
            extra_tools=extra_tools,
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AbodeAIToolsEntry) -> bool:
    """Deregister the LLM API so the entry can be reloaded or removed."""
    entry.runtime_data()
    return True


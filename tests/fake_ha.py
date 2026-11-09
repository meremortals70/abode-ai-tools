"""Dependency-free Home Assistant stubs for the tool tests.

This is intentionally small: enough of the state machine, registries, services,
LLM classes and config-flow classes to exercise this integration. It is not a
general HA emulator and is never imported by the integration itself.

Importing this module installs the stubs in ``sys.modules`` and puts the
integration package on ``sys.path``.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import types
from datetime import datetime
from typing import Any

ROOT = pathlib.Path(__file__).parents[1]
PACKAGE_DIR = ROOT / "custom_components"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))


def _module(name: str, *, package: bool = False) -> types.ModuleType:
    module = types.ModuleType(name)
    if package:
        module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


# ---------------------------------------------------------------------------
# voluptuous (the real package is used when available)
# ---------------------------------------------------------------------------

try:
    import voluptuous as vol
except ModuleNotFoundError:  # pragma: no cover - exercised in CI without HA
    vol = _module("voluptuous")

    class _Schema:
        def __init__(self, schema: Any, **kwargs: Any) -> None:
            self.schema = schema

    def _required(key: Any, **kwargs: Any) -> Any:
        return key

    def _optional(key: Any, **kwargs: Any) -> Any:
        return key

    vol.Schema = _Schema
    vol.Required = _required
    vol.Optional = _optional

# ---------------------------------------------------------------------------
# Home Assistant module tree
# ---------------------------------------------------------------------------

ha = _module("homeassistant", package=True)
components = _module("homeassistant.components", package=True)
component_ha = _module("homeassistant.components.homeassistant", package=True)
exposed = _module("homeassistant.components.homeassistant.exposed_entities")
config_entries = _module("homeassistant.config_entries")
core = _module("homeassistant.core")
helpers = _module("homeassistant.helpers", package=True)
util = _module("homeassistant.util", package=True)
dt = _module("homeassistant.util.dt")
aiohttp_client = _module("homeassistant.helpers.aiohttp_client")
llm_module = _module("homeassistant.helpers.llm")
selector_module = _module("homeassistant.helpers.selector")

ha.components = components
ha.config_entries = config_entries
ha.core = core
ha.helpers = helpers
ha.util = util
components.homeassistant = component_ha
component_ha.exposed_entities = exposed
helpers.aiohttp_client = aiohttp_client
helpers.llm = llm_module
helpers.selector = selector_module


class ConfigEntry:
    def __class_getitem__(cls, item: Any) -> type[ConfigEntry]:
        return cls


class ConfigFlow:
    def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.domain = domain


ConfigFlowResult = dict


class HomeAssistant:
    pass


config_entries.ConfigEntry = ConfigEntry
config_entries.ConfigFlow = ConfigFlow
config_entries.ConfigFlowResult = ConfigFlowResult
core.HomeAssistant = HomeAssistant

# ---------------------------------------------------------------------------
# LLM classes
# ---------------------------------------------------------------------------


class ToolAnnotations:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class ToolResult:
    def __init__(self, data: dict[str, Any], error: bool = False) -> None:
        self.data = data
        self.error = error


class ToolInput:
    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.id = "1"
        self.external = False


class LLMContext:
    def __init__(
        self,
        platform: str = "conversation",
        context: Any = None,
        language: str | None = None,
        assistant: str = "conversation",
        device_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        self.platform = platform
        self.context = context
        self.language = language
        self.assistant = assistant
        self.device_id = device_id
        self.agent_id = agent_id


class Tool:
    name = ""
    title: str | None = None
    description: str | None = None
    parameters = vol.Schema({})
    annotations = ToolAnnotations()
    integration: str | None = None


class API:
    def __init__(
        self,
        hass: Any,
        id: str,
        name: str,
        requires_admin: bool = False,
    ) -> None:
        self.hass = hass
        self.id = id
        self.name = name
        self.requires_admin = requires_admin


class APIInstance:
    def __init__(
        self,
        api: API,
        api_prompt: str,
        llm_context: LLMContext,
        tools: list[Tool],
    ) -> None:
        self.api = api
        self.api_prompt = api_prompt
        self.llm_context = llm_context
        self.tools = tools


def async_register_api(hass: Any, api: API) -> Any:
    return lambda: None


llm_module.Tool = Tool
llm_module.ToolAnnotations = ToolAnnotations
llm_module.ToolResult = ToolResult
llm_module.ToolInput = ToolInput
llm_module.LLMContext = LLMContext
llm_module.API = API
llm_module.APIInstance = APIInstance
llm_module.async_register_api = async_register_api

# ---------------------------------------------------------------------------
# Selectors (config flow)
# ---------------------------------------------------------------------------


class TextSelector:
    def __init__(self, config: Any = None) -> None:
        self.config = config


class TextSelectorConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class TextSelectorType:
    URL = "url"
    PASSWORD = "password"


selector_module.TextSelector = TextSelector
selector_module.TextSelectorConfig = TextSelectorConfig
selector_module.TextSelectorType = TextSelectorType

# ---------------------------------------------------------------------------
# State machine, services and registries
# ---------------------------------------------------------------------------


class State:
    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
        *,
        aliases: tuple[str, ...] = (),
    ) -> None:
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        self.aliases = aliases


class States:
    def __init__(self, states: list[State]) -> None:
        self._states = {state.entity_id: state for state in states}

    def async_all(self, domain: str | None = None) -> list[State]:
        if domain is None:
            return list(self._states.values())
        return [
            state
            for state in self._states.values()
            if state.entity_id.partition(".")[0] == domain
        ]

    def async_entity_ids(self, domain: str | None = None) -> list[str]:
        return [state.entity_id for state in self.async_all(domain)]

    def get(self, entity_id: str) -> State | None:
        return self._states.get(entity_id)


class Services:
    def __init__(self, services: set[tuple[str, str]]) -> None:
        self._services = set(services)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.failures: dict[tuple[str, str], Exception] = {}
        self.delays: dict[tuple[str, str], float] = {}

    def has_service(self, domain: str, name: str) -> bool:
        return (domain, name) in self._services

    async def async_call(
        self,
        domain: str,
        name: str,
        data: dict[str, Any],
        blocking: bool = True,
        context: Any = None,
    ) -> None:
        key = (domain, name)
        if key in self.failures:
            raise self.failures[key]
        delay = self.delays.get(key)
        if delay:
            await asyncio.sleep(delay)
        self.calls.append((domain, name, data))


class FakeHass:
    def __init__(self, states: list[State], services: set[tuple[str, str]]) -> None:
        self.states = States(states)
        self.services = Services(services)
        self.data: dict[str, Any] = {}


class EntityEntry:
    def __init__(
        self,
        area_id: str | None = None,
        device_id: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> None:
        self.area_id = area_id
        self.device_id = device_id
        self.aliases = aliases


class EntityRegistry:
    def __init__(self, entries: dict[str, EntityEntry]) -> None:
        self._entries = entries

    def async_get(self, entity_id: str) -> EntityEntry | None:
        return self._entries.get(entity_id)


class DeviceRegistry:
    def async_get(self, device_id: str) -> None:
        return None


class Area:
    def __init__(
        self,
        area_id: str,
        name: str,
        aliases: tuple[str, ...] = (),
    ) -> None:
        self.id = area_id
        self.name = name
        self.aliases = list(aliases)


class AreaRegistry:
    def __init__(self, areas: list[Area]) -> None:
        self._areas = {area.id: area for area in areas}

    def async_list_areas(self) -> list[Area]:
        return list(self._areas.values())

    def async_get_area(self, area_id: str) -> Area | None:
        return self._areas.get(area_id)


AREAS = [
    Area("kitchen", "Kitchen"),
    Area("hall", "Hall"),
    Area("garden", "Garden"),
    Area("den", "Den"),
    Area("lounge", "Lounge Room", aliases=("TV room",)),
]

ENTRIES = {
    "light.kitchen": EntityEntry(area_id="kitchen", aliases=("big light",)),
    "lock.front": EntityEntry(area_id="hall"),
    "automation.security": EntityEntry(area_id="hall"),
    "person.jason": EntityEntry(area_id="hall"),
    "sensor.long": EntityEntry(area_id="kitchen"),
    "cover.garage": EntityEntry(area_id="garden"),
    "weather.home": EntityEntry(area_id="garden"),
    "calendar.house": EntityEntry(area_id="hall"),
    "device_tracker.phone": EntityEntry(area_id="hall"),
    "script.morning": EntityEntry(area_id="hall"),
}

ENTITY_REGISTRY = EntityRegistry(ENTRIES)
DEVICE_REGISTRY = DeviceRegistry()
AREA_REGISTRY = AreaRegistry(AREAS)

helpers.area_registry = _module("homeassistant.helpers.area_registry")
helpers.device_registry = _module("homeassistant.helpers.device_registry")
helpers.entity_registry = _module("homeassistant.helpers.entity_registry")
helpers.area_registry.async_get = lambda hass: AREA_REGISTRY
helpers.device_registry.async_get = lambda hass: DEVICE_REGISTRY
helpers.entity_registry.async_get = lambda hass: ENTITY_REGISTRY

EXPOSED: dict[str, set[str]] = {
    "conversation": set(ENTRIES),
    "ai_task": set(),
}


def async_should_expose(hass: Any, assistant: str, entity_id: str) -> bool:
    return entity_id in EXPOSED.get(assistant, set())


exposed.async_should_expose = async_should_expose

dt.now = lambda: datetime(2026, 11, 9, 12, 34, 56)

SESSION: Any = None


def async_get_clientsession(hass: Any) -> Any:
    return SESSION


aiohttp_client.async_get_clientsession = async_get_clientsession

# ---------------------------------------------------------------------------
# Fake HTTP client for Paperless tests
# ---------------------------------------------------------------------------


class FakeContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def read(self, limit: int = -1) -> bytes:
        if limit < 0:
            return self.body
        return self.body[:limit]


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        content_type: str = "application/json",
        content_length: int | None = None,
        charset: str = "utf-8",
    ) -> None:
        self.content = FakeContent(body)
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.content_length = content_length
        self.charset = charset

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.last_request: dict[str, Any] = {}

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.last_request = {"url": url, **kwargs}
        return self.response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SERVICE_SET = {
    ("homeassistant", "turn_on"),
    ("homeassistant", "turn_off"),
    ("homeassistant", "toggle"),
    ("homeassistant", "reload_config_entry"),
    ("homeassistant", "save_persistent_states"),
    ("light", "turn_on"),
    ("light", "turn_off"),
    ("light", "toggle"),
    ("lock", "lock"),
    ("lock", "unlock"),
    ("lock", "open"),
    ("cover", "open_cover"),
    ("cover", "close_cover"),
    ("cover", "toggle"),
    ("automation", "turn_on"),
    ("scene", "turn_on"),
    ("script", "turn_on"),
    ("script", "reload"),
    ("media_player", "clear_playlist"),
    ("vacuum", "send_command"),
}


def default_states() -> list[State]:
    return [
        State(
            "light.kitchen",
            "on",
            {
                "friendly_name": "Kitchen Light",
                "brightness": 120,
                "color_mode": "xy",
                "effect_list": ["rainbow", "fire"],
                "supported_color_modes": ["xy"],
            },
            aliases=("big light",),
        ),
        State("lock.front", "locked", {"friendly_name": "Front Door"}),
        State("automation.security", "on", {"friendly_name": "Security"}),
        State(
            "person.jason",
            "home",
            {
                "friendly_name": "Jason",
                "latitude": 1.23,
                "longitude": 4.56,
                "gps_accuracy": 5,
                "source": "gps",
                "user_id": "abc",
            },
        ),
        State(
            "sensor.long",
            "x" * 500,
            {"friendly_name": "y" * 200, "unit_of_measurement": "%"},
        ),
        State(
            "cover.garage",
            "closed",
            {"friendly_name": "Garage", "current_position": 0},
        ),
        State(
            "weather.home",
            "sunny",
            {
                "friendly_name": "Weather",
                "temperature": 20,
                "humidity": 50,
                "pressure": 1000,
                "wind_speed": 5,
                "visibility": 10,
                "forecast": [{"temperature": 21}],
            },
        ),
        State(
            "calendar.house",
            "off",
            {
                "friendly_name": "Calendar",
                "message": "Dentist",
                "start_time": "2026-11-10 09:00",
                "end_time": "2026-11-10 10:00",
                "all_day": False,
                "description": "secret",
                "location": "clinic",
            },
        ),
        State(
            "device_tracker.phone",
            "home",
            {
                "friendly_name": "Phone",
                "latitude": 1.23,
                "longitude": 4.56,
            },
        ),
        State("script.morning", "off", {"friendly_name": "Morning"}),
    ]


def build_hass() -> FakeHass:
    return FakeHass(default_states(), SERVICE_SET)


def make_context(assistant: str = "conversation") -> LLMContext:
    return LLMContext(assistant=assistant)


def make_input(tool_name: str, arguments: dict[str, Any]) -> ToolInput:
    return ToolInput(tool_name, arguments)


class Entry:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {}
        self.runtime_data: Any = None

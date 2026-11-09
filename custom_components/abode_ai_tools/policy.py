"""Pure policy for the bounded tool surface.

This module deliberately imports nothing from Home Assistant. The allowlists,
attribute projection and limits can therefore be unit-tested without the HA
test harness, and the intent stays readable in one place.

Changing anything here changes what the model is allowed to do. Treat it as a
security boundary, not as configuration.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------

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

SENSITIVE_DOMAINS = frozenset({"cover", "lock", "valve"})
"""Domains whose actions can have physical or security consequences. The
system prompt asks the model to act on these only on an explicit request."""

# ---------------------------------------------------------------------------
# Explicit service allowlist. A domain allowlist is not enough: the
# `homeassistant` domain contains reload_config_entry, save_persistent_states
# and other services that accept an entity_id. Only the services below may be
# called, and only on an entity in CONTROLLABLE_DOMAINS.
# ---------------------------------------------------------------------------

_TURN = frozenset({"turn_on", "turn_off", "toggle"})

ALLOWED_SERVICES: dict[str, frozenset[str]] = {
    "homeassistant": _TURN,
    "light": _TURN,
    "switch": _TURN,
    "fan": _TURN,
    "input_boolean": _TURN,
    "humidifier": _TURN,
    "climate": _TURN,
    "water_heater": frozenset({"turn_on", "turn_off"}),
    "media_player": frozenset(
        {
            "turn_on",
            "turn_off",
            "toggle",
            "volume_up",
            "volume_down",
            "media_play",
            "media_pause",
            "media_play_pause",
            "media_stop",
            "media_next_track",
            "media_previous_track",
        }
    ),
    "cover": frozenset(
        {
            "open_cover",
            "close_cover",
            "stop_cover",
            "toggle",
            "open_cover_tilt",
            "close_cover_tilt",
            "stop_cover_tilt",
            "toggle_cover_tilt",
        }
    ),
    # lock.open releases the latch; it is deliberately not permitted.
    "lock": frozenset({"lock", "unlock"}),
    "valve": frozenset({"open_valve", "close_valve", "toggle"}),
    "vacuum": frozenset(
        {
            "turn_on",
            "turn_off",
            "toggle",
            "start",
            "pause",
            "stop",
            "return_to_base",
            "locate",
            "clean_spot",
            "start_pause",
        }
    ),
    "scene": frozenset({"turn_on"}),
    "script": _TURN,
    "button": frozenset({"press"}),
}

# ---------------------------------------------------------------------------
# Attribute projection for get_entity_state. Only these keys are returned, so
# GPS coordinates, calendar descriptions and large lists such as weather
# forecasts or media source lists never reach the model.
# ---------------------------------------------------------------------------

ATTRIBUTE_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "calendar": ("message", "start_time", "end_time", "all_day"),
    "climate": (
        "current_temperature",
        "temperature",
        "hvac_action",
        "hvac_mode",
        "fan_mode",
        "preset_mode",
        "humidity",
        "swing_mode",
    ),
    "cover": ("current_position", "current_tilt_position"),
    "fan": ("percentage", "preset_mode", "oscillating", "direction"),
    "humidifier": ("humidity", "mode", "target_humidity"),
    "light": ("brightness", "color_mode", "color_temp_kelvin", "effect"),
    "media_player": (
        "media_title",
        "media_artist",
        "media_album_name",
        "source",
        "volume_level",
        "is_volume_muted",
        "media_duration",
        "media_position",
    ),
    "sensor": ("unit_of_measurement",),
    "sun": (
        "next_dawn",
        "next_dusk",
        "next_rising",
        "next_setting",
        "elevation",
        "azimuth",
    ),
    "vacuum": ("battery_level", "fan_speed", "status"),
    "valve": ("current_position",),
    "water_heater": (
        "current_temperature",
        "temperature",
        "operation_mode",
        "away_mode",
    ),
    "weather": ("temperature", "humidity", "pressure", "wind_speed", "visibility"),
}

# ---------------------------------------------------------------------------
# Bounds. These are the whole point of this component: every one of them
# bounds a value that would otherwise be unbounded. Change deliberately.
# ---------------------------------------------------------------------------

MAX_RESULTS = 20
"""Maximum entity records returned by search_entities, ever."""

MAX_ATTRIBUTES = 6
"""Maximum attributes returned by get_entity_state."""

MAX_ENTITY_ID_CHARS = 80
MAX_NAME_CHARS = 80
MAX_AREA_CHARS = 40
MAX_STATE_CHARS = 120
MAX_ATTRIBUTE_CHARS = 200
MAX_KNOWN_AREAS = 30


def entity_domain(entity_id: str) -> str:
    """Return the domain part of an entity_id, normalised."""
    return entity_id.partition(".")[0].strip().lower()


def entity_controllable(entity_id: str) -> bool:
    """Return True if call_service may target this entity's domain."""
    return entity_domain(entity_id) in CONTROLLABLE_DOMAINS


def service_allowed(domain: str, service: str) -> bool:
    """Return True if this exact service is on the allowlist."""
    return service in ALLOWED_SERVICES.get(domain, frozenset())


def service_matches_entity(domain: str, entity_id: str) -> bool:
    """Return True if a service domain may act on this entity.

    The generic homeassistant turn services dispatch by entity domain, so they
    are allowed here and checked against the entity's own domain in the tool.
    Every other service must match the entity domain, which stops calls such as
    light.turn_on against a lock.
    """
    return domain == "homeassistant" or domain == entity_domain(entity_id)


def attributes_for(entity_id: str) -> tuple[str, ...]:
    """Return the safe attribute names for an entity's domain."""
    return ATTRIBUTE_ALLOWLIST.get(entity_domain(entity_id), ())

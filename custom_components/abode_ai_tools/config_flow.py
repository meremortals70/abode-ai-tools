"""Config flow for Abode AI Tools.

One entry only (`single_config_entry` in the manifest). Both fields are
optional: submitting an empty form gives the four device-control tools and
no network calls, which is exactly what the component did before it had a
flow. Filling in the URL adds the Paperless document tools.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_PAPERLESS_TOKEN, CONF_PAPERLESS_URL, DOMAIN

STEP_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PAPERLESS_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_PAPERLESS_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop blank fields so `entry.data.get(...)` is None, not empty string."""
    return {k: v for k, v in user_input.items() if v not in (None, "")}


class AbodeAIToolsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Abode AI Tools config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single entry."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_SCHEMA)

        return self.async_create_entry(title="Abode AI Tools", data=_clean(user_input))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the Paperless endpoint without removing the entry."""
        entry = self._get_reconfigure_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_SCHEMA, entry.data
                ),
            )

        return self.async_update_reload_and_abort(entry, data=_clean(user_input))

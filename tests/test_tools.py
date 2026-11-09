"""Behaviour tests for the tool classes using the dependency-free fake HA."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tests import fake_ha

import abode_ai_tools as integration  # noqa: E402 - fake_ha sets sys.path


class ToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.hass = fake_ha.build_hass()

    async def _search(self, arguments: dict, assistant: str = "conversation"):
        return await integration.SearchEntitiesTool().async_call(
            self.hass,
            fake_ha.make_input("search_entities", arguments),
            fake_ha.make_context(assistant),
        )

    async def _get(self, entity_id: str):
        return await integration.GetEntityStateTool().async_call(
            self.hass,
            fake_ha.make_input("get_entity_state", {"entity_id": entity_id}),
            fake_ha.make_context(),
        )

    async def _call(self, service: str, entity_id: str):
        return await integration.CallServiceTool().async_call(
            self.hass,
            fake_ha.make_input(
                "call_service",
                {"service": service, "entity_id": entity_id},
            ),
            fake_ha.make_context(),
        )

    async def test_exposure_follows_assistant(self) -> None:
        conversation = await self._search({})
        ai_task = await self._search({}, assistant="ai_task")
        self.assertEqual(conversation.data["count"], 9)
        self.assertEqual(ai_task.data["count"], 0)

    async def test_search_matches_alias(self) -> None:
        result = await self._search({"query": "big light"})
        self.assertEqual(result.data["count"], 1)
        self.assertEqual(
            result.data["results"][0]["entity_id"], "light.kitchen"
        )

    async def test_search_caps_long_fields(self) -> None:
        result = await self._search({"query": "long"})
        self.assertEqual(result.data["count"], 1)
        record = result.data["results"][0]
        self.assertLessEqual(len(record["name"]), 80)
        self.assertLessEqual(len(record["state"]), 120)
        self.assertLessEqual(len(record["area"]), 40)
        self.assertLessEqual(len(record["entity_id"]), 80)

    async def test_area_matching_uses_word_boundaries(self) -> None:
        # "den" must not match the Garden area, which contains two entities.
        result = await self._search({"area": "den"})
        self.assertEqual(result.data["count"], 0)

    async def test_unknown_domain_is_an_explicit_error(self) -> None:
        result = await self._search({"domain": "automation"})
        self.assertTrue(result.error)
        self.assertIn("not searchable", result.data["error"])
        self.assertEqual(result.data["results"], [])

    async def test_person_has_no_location_attributes(self) -> None:
        result = await self._get("person.jason")
        self.assertEqual(result.data["attributes"], {})

    async def test_device_tracker_has_no_location_attributes(self) -> None:
        result = await self._get("device_tracker.phone")
        self.assertEqual(result.data["attributes"], {})

    async def test_light_returns_useful_attributes_only(self) -> None:
        result = await self._get("light.kitchen")
        self.assertEqual(result.data["attributes"]["brightness"], 120)
        self.assertIn("color_mode", result.data["attributes"])
        self.assertNotIn("effect_list", result.data["attributes"])
        self.assertNotIn("supported_color_modes", result.data["attributes"])

    async def test_weather_excludes_forecast(self) -> None:
        result = await self._get("weather.home")
        self.assertIn("temperature", result.data["attributes"])
        self.assertNotIn("forecast", result.data["attributes"])

    async def test_calendar_excludes_description_and_location(self) -> None:
        result = await self._get("calendar.house")
        self.assertIn("message", result.data["attributes"])
        self.assertNotIn("description", result.data["attributes"])
        self.assertNotIn("location", result.data["attributes"])

    async def test_sensor_state_and_attribute_are_capped(self) -> None:
        result = await self._get("sensor.long")
        self.assertLessEqual(len(result.data["state"]), 120)
        self.assertLessEqual(
            len(result.data["attributes"]["unit_of_measurement"]), 200
        )

    async def test_blocked_services_and_entities(self) -> None:
        blocked = [
            ("homeassistant.reload_config_entry", "light.kitchen"),
            ("homeassistant.save_persistent_states", "light.kitchen"),
            ("homeassistant.turn_on", "automation.security"),
            ("automation.turn_on", "automation.security"),
            ("light.turn_on", "lock.front"),
            ("lock.open", "lock.front"),
            ("script.reload", "script.morning"),
            ("media_player.clear_playlist", "light.kitchen"),
        ]
        for service, entity_id in blocked:
            result = await self._call(service, entity_id)
            self.assertTrue(result.error, (service, result.data))

    async def test_allowed_services(self) -> None:
        allowed = [
            ("homeassistant.turn_on", "light.kitchen"),
            ("light.turn_on", "light.kitchen"),
            ("homeassistant.toggle", "cover.garage"),
            ("lock.unlock", "lock.front"),
            ("cover.open_cover", "cover.garage"),
            ("script.turn_on", "script.morning"),
        ]
        for service, entity_id in allowed:
            result = await self._call(service, entity_id)
            self.assertFalse(result.error, (service, result.data))

        self.assertEqual(
            [call[:2] for call in self.hass.services.calls],
            [tuple(service.split(".", 1)) for service, _ in allowed],
        )

    async def test_generic_turn_on_cover_is_rejected(self) -> None:
        result = await self._call("homeassistant.turn_on", "cover.garage")
        self.assertTrue(result.error)
        self.assertIn("not supported", result.data["error"])

    async def test_service_timeout_returns_error(self) -> None:
        self.hass.services.delays[("light", "turn_on")] = 0.05
        with patch.object(integration, "SERVICE_CALL_TIMEOUT", 0.01):
            result = await self._call("light.turn_on", "light.kitchen")
        self.assertTrue(result.error)
        self.assertIn("timed out", result.data["error"])
        self.assertEqual(self.hass.services.calls, [])

    async def test_service_failure_reason_is_returned(self) -> None:
        self.hass.services.failures[("light", "turn_on")] = ValueError("boom")
        result = await self._call("light.turn_on", "light.kitchen")
        self.assertTrue(result.error)
        self.assertIn("boom", result.data["error"])

    async def test_api_prompt_mentions_untrusted_data(self) -> None:
        api = integration.AbodeAIToolsAPI(
            hass=self.hass,
            id=integration.DOMAIN,
            name="Abode AI Tools",
        )
        instance = await api.async_get_api_instance(fake_ha.make_context())
        self.assertIn("untrusted", instance.api_prompt)
        self.assertIn("sensitive", instance.api_prompt)

    async def test_setup_and_unload_are_idempotent(self) -> None:
        entry = fake_ha.Entry(
            {
                "paperless_url": "http://paperless.local/mcp",
                "paperless_token": "secret",
            }
        )
        self.assertTrue(await integration.async_setup_entry(self.hass, entry))
        self.assertTrue(callable(entry.runtime_data))
        self.assertTrue(await integration.async_unload_entry(self.hass, entry))
        self.assertIsNone(entry.runtime_data)
        # A second unload must not raise KeyError from the core unregister.
        self.assertTrue(await integration.async_unload_entry(self.hass, entry))


if __name__ == "__main__":
    unittest.main()

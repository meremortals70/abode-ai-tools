"""Tests for the pure policy module.

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

import policy  # noqa: E402 - path is set above


class ServiceAllowlistTests(unittest.TestCase):
    """A domain allowlist is not enough; the exact service matters."""

    def test_homeassistant_turn_services_are_allowed(self) -> None:
        for service in ("turn_on", "turn_off", "toggle"):
            self.assertTrue(policy.service_allowed("homeassistant", service))

    def test_homeassistant_admin_services_are_blocked(self) -> None:
        for service in (
            "reload_config_entry",
            "save_persistent_states",
            "restart",
            "stop",
            "reload_all",
            "reload_core_config",
            "update_entity",
        ):
            self.assertFalse(policy.service_allowed("homeassistant", service))

    def test_other_domains_cannot_be_reached_through_homeassistant(self) -> None:
        self.assertFalse(policy.service_allowed("automation", "turn_on"))
        self.assertFalse(policy.service_allowed("recorder", "purge"))
        self.assertFalse(policy.service_allowed("backup", "create"))

    def test_dangerous_controllable_services_are_blocked(self) -> None:
        self.assertFalse(policy.service_allowed("lock", "open"))
        self.assertFalse(policy.service_allowed("script", "reload"))
        self.assertFalse(policy.service_allowed("media_player", "clear_playlist"))
        self.assertFalse(policy.service_allowed("vacuum", "send_command"))

    def test_expected_everyday_services_are_allowed(self) -> None:
        self.assertTrue(policy.service_allowed("light", "turn_on"))
        self.assertTrue(policy.service_allowed("cover", "open_cover"))
        self.assertTrue(policy.service_allowed("lock", "unlock"))
        self.assertTrue(policy.service_allowed("scene", "turn_on"))
        self.assertTrue(policy.service_allowed("button", "press"))

    def test_every_controllable_domain_has_an_allowlist(self) -> None:
        self.assertLessEqual(
            set(policy.CONTROLLABLE_DOMAINS), set(policy.ALLOWED_SERVICES)
        )


class EntityPolicyTests(unittest.TestCase):
    """Entity-domain checks close the generic homeassistant service bypass."""

    def test_entity_domain_is_normalised(self) -> None:
        self.assertEqual(policy.entity_domain("light.kitchen"), "light")
        self.assertEqual(policy.entity_domain("Light.Kitchen"), "light")
        self.assertEqual(policy.entity_domain("not-an-entity"), "not-an-entity")

    def test_controllable_domains(self) -> None:
        self.assertTrue(policy.entity_controllable("light.kitchen"))
        self.assertTrue(policy.entity_controllable("script.morning"))
        self.assertFalse(policy.entity_controllable("automation.security"))
        self.assertFalse(policy.entity_controllable("input_text.secret"))
        self.assertFalse(policy.entity_controllable("sensor.temperature"))

    def test_service_entity_match(self) -> None:
        self.assertTrue(policy.service_matches_entity("light", "light.kitchen"))
        self.assertTrue(
            policy.service_matches_entity("homeassistant", "automation.security")
        )
        self.assertFalse(policy.service_matches_entity("light", "lock.front"))
        self.assertFalse(policy.service_matches_entity("lock", "light.kitchen"))

    def test_sensitive_domains_are_controllable(self) -> None:
        self.assertLessEqual(
            policy.SENSITIVE_DOMAINS, set(policy.CONTROLLABLE_DOMAINS)
        )


class AttributePolicyTests(unittest.TestCase):
    """The projection must not leak location or large structures."""

    def test_person_and_device_tracker_have_no_attributes(self) -> None:
        self.assertEqual(policy.attributes_for("person.jason"), ())
        self.assertEqual(policy.attributes_for("device_tracker.phone"), ())

    def test_light_attributes_are_useful_and_safe(self) -> None:
        attributes = policy.attributes_for("light.kitchen")
        self.assertIn("brightness", attributes)
        self.assertNotIn("latitude", attributes)
        self.assertNotIn("longitude", attributes)
        self.assertNotIn("effect_list", attributes)

    def test_weather_excludes_forecast(self) -> None:
        attributes = policy.attributes_for("weather.home")
        self.assertIn("temperature", attributes)
        self.assertNotIn("forecast", attributes)

    def test_calendar_excludes_description_and_location(self) -> None:
        attributes = policy.attributes_for("calendar.house")
        self.assertIn("message", attributes)
        self.assertNotIn("description", attributes)
        self.assertNotIn("location", attributes)

    def test_media_player_excludes_large_lists(self) -> None:
        attributes = policy.attributes_for("media_player.living_room")
        self.assertIn("media_title", attributes)
        self.assertNotIn("source_list", attributes)
        self.assertNotIn("sound_mode_list", attributes)
        self.assertNotIn("entity_picture", attributes)


if __name__ == "__main__":
    unittest.main()

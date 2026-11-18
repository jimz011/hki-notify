"""Regression tests with lightweight Home Assistant lifecycle/service doubles.

Run with: python -m unittest discover -s tests -v
Requires voluptuous; a running Home Assistant instance is not needed.
"""

import importlib
import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


class RestoreEntity:
    """Minimal entity lifecycle boundary for exercising integration code."""

    @property
    def unique_id(self):
        return self._attr_unique_id

    async def async_added_to_hass(self):
        pass

    async def async_get_last_state(self):
        return None

    def async_entity_id_changed(self, old_entity_id):
        self.last_old_entity_id = old_entity_id

    def schedule_update_ha_state(self, force_refresh=False):
        pass


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    return result


class EntityIdChangesTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cv = module(
            "homeassistant.helpers.config_validation",
            config_entry_only_config_schema=lambda domain: {},
            string=str, boolean=bool, entity_ids=lambda value: value,
            ensure_list=lambda value: value if isinstance(value, list) else [value],
        )
        modules = {
            "homeassistant": module("homeassistant"),
            "homeassistant.core": module(
                "homeassistant.core", HomeAssistant=object, ServiceCall=object,
                callback=lambda method: method,
            ),
            "homeassistant.config_entries": module(
                "homeassistant.config_entries", ConfigEntry=object,
            ),
            "homeassistant.helpers": module(
                "homeassistant.helpers", config_validation=cv,
            ),
            cv.__name__: cv,
            "homeassistant.helpers.restore_state": module(
                "homeassistant.helpers.restore_state", RestoreEntity=RestoreEntity,
            ),
            "homeassistant.util": module("homeassistant.util"),
            "homeassistant.util.dt": module(
                "homeassistant.util.dt", now=lambda: datetime.now(timezone.utc),
            ),
        }
        with patch.dict(sys.modules, modules):
            cls.integration = importlib.import_module("custom_components.hki_notify")
            cls.sensor_module = importlib.import_module("custom_components.hki_notify.sensor")

    async def asyncSetUp(self):
        self.handlers = {}
        self.hass = SimpleNamespace(
            data={},
            services=SimpleNamespace(async_register=self.register_service),
            config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
        )
        self.entry = SimpleNamespace(entry_id="main", title="Main")
        await self.integration.async_setup_entry(self.hass, self.entry)
        self.sensor = await self.add_sensor(self.entry, "sensor.main")
        self.other = await self.add_sensor(
            SimpleNamespace(entry_id="other", title="Other"), "sensor.other",
        )

    def register_service(self, domain, service, handler, schema):
        self.handlers[service] = (handler, schema)

    async def add_sensor(self, entry, entity_id):
        sensor = self.sensor_module.HKINotifySensor(self.hass, entry)
        sensor.entity_id = entity_id
        sensor.schedule_update_ha_state = Mock()
        await sensor.async_added_to_hass()
        return sensor

    def call(self, service, **data):
        handler, schema = self.handlers[service]
        handler(SimpleNamespace(data=schema(data)))

    def rename(self, new_id):
        old_id = self.sensor.entity_id
        self.sensor.entity_id = new_id
        self.sensor.async_entity_id_changed(old_id)
        self.assertEqual(self.sensor.last_old_entity_id, old_id)

    async def test_create_and_dismiss_after_repeated_in_place_renames(self):
        self.call("create", entity_id="sensor.main", id="one", message="Keep me")
        self.rename("sensor.renamed")
        self.rename("sensor.final")
        self.assertEqual(self.sensor.state, 1)
        self.call("create", entity_id=["sensor.final"], id="two", message="New")
        self.assertEqual(self.sensor.state, 2)
        self.assertEqual(self.other.state, 0)
        self.call("dismiss", entity_id="sensor.final", id="one")
        self.assertEqual(self.sensor.extra_state_attributes["messages"][0]["id"], "two")
        self.call("dismiss_all", entity_id=["sensor.final"])
        self.assertEqual(self.sensor.state, 0)

    async def test_old_and_unknown_ids_do_not_target_renamed_sensor(self):
        self.rename("sensor.renamed")
        self.call("create", entity_id="sensor.renamed", id="one", message="Keep")
        for entity_id in ("sensor.main", "sensor.missing"):
            self.call("create", entity_id=entity_id, id="two", message="Ignore")
            self.call("dismiss", entity_id=entity_id, id="one")
            self.call("dismiss_all", entity_id=entity_id)
        self.assertEqual(self.sensor.state, 1)
        self.assertEqual(self.other.state, 0)

    async def test_broadcast_and_multiple_targets_after_rename(self):
        self.rename("sensor.renamed")
        self.call("create", id="all", message="Broadcast")
        self.assertEqual((self.sensor.state, self.other.state), (1, 1))
        self.call("dismiss", entity_id=["sensor.renamed", "sensor.other"], id="all")
        self.assertEqual((self.sensor.state, self.other.state), (0, 0))
        self.call("create", id="all", message="Broadcast")
        self.call("dismiss_all")
        self.assertEqual((self.sensor.state, self.other.state), (0, 0))

    async def test_unload_and_readd_after_rename(self):
        self.rename("sensor.renamed")
        await self.sensor.async_will_remove_from_hass()
        self.call("create", id="all", message="Only the other sensor")
        self.assertEqual((self.sensor.state, self.other.state), (0, 1))
        self.assertNotIn(self.sensor, self.hass.data["hki_notify"]["entities"].values())
        await self.sensor.async_added_to_hass()
        self.call("create", entity_id="sensor.renamed", id="new", message="Readded")
        self.assertEqual(self.sensor.state, 1)


if __name__ == "__main__":
    unittest.main()

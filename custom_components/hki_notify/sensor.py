import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([HKINotifySensor(hass, config_entry)])

class HKINotifySensor(RestoreEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry_id = entry.entry_id
        self._attr_name = entry.title 
        self._attr_unique_id = f"hki_notify_{entry.entry_id}"
        self._messages = []

    async def async_added_to_hass(self):
        """Register self and restore state."""
        await super().async_added_to_hass()
        
        # Register in global registry
        if DOMAIN not in self._hass.data:
            self._hass.data[DOMAIN] = {"entities": {}}
        self._hass.data[DOMAIN]["entities"][self.entity_id] = self

        # Restore
        state = await self.async_get_last_state()
        if state and "messages" in state.attributes:
            self._messages = state.attributes["messages"]

    async def async_will_remove_from_hass(self):
        if DOMAIN in self._hass.data and "entities" in self._hass.data[DOMAIN]:
            self._hass.data[DOMAIN]["entities"].pop(self.entity_id, None)

    def add_message(self, msg):
        """Add or update a message. Creates a NEW list to force state update."""
        new_list = list(self._messages) # Copy list
        
        updated = False
        for i, m in enumerate(new_list):
            if m["id"] == msg["id"]:
                # Merge old and new data, replacing the dict
                new_list[i] = {**m, **msg}
                updated = True
                break
        
        if not updated:
            new_list.append(msg)
            
        self._messages = new_list
        self.schedule_update_ha_state(True)

    def remove_message(self, msg_id):
        """Remove a message."""
        initial_len = len(self._messages)
        # Create new list via comprehension
        self._messages = [m for m in self._messages if m["id"] != msg_id]
        
        if len(self._messages) != initial_len:
            self.schedule_update_ha_state(True)

    def clear_all_messages(self):
        """Clear all messages."""
        if len(self._messages) > 0:
            self._messages = []
            self.schedule_update_ha_state(True)

    @property
    def state(self):
        return len(self._messages)

    @property
    def extra_state_attributes(self):
        return { "messages": self._messages }

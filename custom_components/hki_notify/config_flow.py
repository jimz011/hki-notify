import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class HkiNotifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HKI Notify."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # User input name: "Kitchen" -> Title: "HKI Notify Kitchen"
            # This results in entity_id: sensor.hki_notify_kitchen
            name = user_input.get("name", "Main")
            title = f"HKI Notify {name}"
            
            # Create the entry (No check for existing entries here!)
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("name", default="Main"): str
            }),
            errors=errors
        )

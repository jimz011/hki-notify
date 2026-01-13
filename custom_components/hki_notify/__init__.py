import logging
import voluptuous as vol
import homeassistant.util.dt as dt_util  # <--- NEW IMPORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

# Services
SERVICE_CREATE = "create"
SERVICE_DISMISS = "dismiss"
SERVICE_DISMISS_ALL = "dismiss_all"

# Core attributes
ATTR_ENTITY_ID = "entity_id"
ATTR_ID = "id"
ATTR_MESSAGE = "message"
ATTR_ICON = "icon"
ATTR_ICON_SPIN = "icon_spin"
ATTR_TIMESTAMP = "timestamp"  # <--- NEW CONSTANT

# Color attributes
ATTR_TEXT_COLOR = "text_color"
ATTR_ICON_COLOR = "icon_color"
ATTR_BG_COLOR = "bg_color"
ATTR_BORDER_COLOR = "border_color"

# Typography attributes
ATTR_FONT_SIZE = "font_size"
ATTR_FONT_WEIGHT = "font_weight"
ATTR_FONT_FAMILY = "font_family"

# Border & Shadow attributes
ATTR_BORDER_RADIUS = "border_radius"
ATTR_BORDER_WIDTH = "border_width"
ATTR_BOX_SHADOW = "box_shadow"

# Layout attributes
ATTR_ALIGNMENT = "alignment"

# Action attributes
ATTR_TAP_ACTION = "tap_action"
ATTR_ACTION_TYPE = "action_type"
ATTR_NAVIGATION_PATH = "navigation_path" 
ATTR_SERVICE_ACTION = "service_action"

# Confirmation attributes
ATTR_CONFIRM = "confirm"
ATTR_CONFIRM_MESSAGE = "confirm_message"

# Tap Action Schema
TAP_ACTION_SCHEMA = vol.Schema({
    vol.Required("action"): cv.string,
    vol.Optional("navigation_path"): cv.string,
    vol.Optional("url_path"): cv.string,
    vol.Optional("service"): cv.string,
    vol.Optional("service_data"): dict,
    vol.Optional("data"): dict,
    vol.Optional("target"): dict,
}, extra=vol.ALLOW_EXTRA)

# Create Schema
CREATE_SCHEMA = vol.Schema({
    # Targeting
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    
    # Required
    vol.Required(ATTR_ID): cv.string,
    vol.Required(ATTR_MESSAGE): cv.string,
    
    # Icon
    vol.Optional(ATTR_ICON, default="mdi:bell"): cv.string,
    vol.Optional(ATTR_ICON_SPIN, default=False): cv.boolean,
    
    # NEW: Optional timestamp override
    vol.Optional(ATTR_TIMESTAMP): cv.string,

    # Colors
    vol.Optional(ATTR_TEXT_COLOR): vol.Any(cv.string, list),
    vol.Optional(ATTR_ICON_COLOR): vol.Any(cv.string, list),
    vol.Optional(ATTR_BG_COLOR): vol.Any(cv.string, list),
    vol.Optional(ATTR_BORDER_COLOR): vol.Any(cv.string, list),
    
    # Typography
    vol.Optional(ATTR_FONT_SIZE): vol.Coerce(int),
    vol.Optional(ATTR_FONT_WEIGHT): vol.In(["Light", "Regular", "Medium", "Semi Bold", "Bold", "Extra Bold"]),
    vol.Optional(ATTR_FONT_FAMILY): cv.string,
    
    # Border & Shadow
    vol.Optional(ATTR_BORDER_RADIUS): vol.Coerce(int),
    vol.Optional(ATTR_BORDER_WIDTH): vol.Coerce(int),
    vol.Optional(ATTR_BOX_SHADOW): cv.string,
    
    # Layout
    vol.Optional(ATTR_ALIGNMENT): vol.In(["left", "center", "right"]),
    
    # Actions
    vol.Optional(ATTR_TAP_ACTION): TAP_ACTION_SCHEMA,
    vol.Optional(ATTR_ACTION_TYPE): vol.In(["navigate", "url", "call-service", "none"]),
    vol.Optional(ATTR_NAVIGATION_PATH): cv.string,
    vol.Optional(ATTR_SERVICE_ACTION): cv.ensure_list,
    
    # Confirmation
    vol.Optional(ATTR_CONFIRM): cv.boolean,
    vol.Optional(ATTR_CONFIRM_MESSAGE): cv.string,
})

# Dismiss Schema
DISMISS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_ID): cv.string,
})

# Dismiss All Schema
DISMISS_ALL_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"entities": {}}
    
    def get_targets(call):
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        registry = hass.data[DOMAIN]["entities"]
        targets = []
        if entity_ids:
            if isinstance(entity_ids, str): entity_ids = [entity_ids]
            for eid in entity_ids:
                if eid in registry:
                    targets.append(registry[eid])
        else:
            targets = list(registry.values())
        return targets

    def handle_create(call: ServiceCall):
        # NEW: Handle Timestamp logic
        # Use provided timestamp or current time (ISO Format)
        ts = call.data.get(ATTR_TIMESTAMP)
        if not ts:
            ts = dt_util.now().isoformat()

        new_msg = {
            "id": call.data[ATTR_ID],
            "message": call.data[ATTR_MESSAGE],
            "icon": call.data[ATTR_ICON],
            "icon_spin": call.data[ATTR_ICON_SPIN],
            "timestamp": ts,  # <--- Added here
        }
        
        # 1. Handle Colors
        color_attrs = [ATTR_TEXT_COLOR, ATTR_ICON_COLOR, ATTR_BG_COLOR, ATTR_BORDER_COLOR]
        for attr in color_attrs:
            if attr in call.data:
                val = call.data[attr]
                if isinstance(val, list) and len(val) == 3:
                    new_msg[attr] = f"rgb({val[0]}, {val[1]}, {val[2]})"
                else:
                    new_msg[attr] = val
        
        # 2. Handle Typography, Border, Layout
        direct_attrs = [
            ATTR_FONT_SIZE, ATTR_FONT_WEIGHT, ATTR_FONT_FAMILY,
            ATTR_BORDER_RADIUS, ATTR_BORDER_WIDTH, ATTR_BOX_SHADOW,
            ATTR_ALIGNMENT
        ]
        for attr in direct_attrs:
            if attr in call.data:
                new_msg[attr] = call.data[attr]

        # 3. Handle Actions
        action_type = call.data.get(ATTR_ACTION_TYPE)
        
        # FIX: Auto-detect 'call-service' if not set but service data is present
        if not action_type and call.data.get(ATTR_SERVICE_ACTION):
            action_type = "call-service"
        
        if action_type:
            action_obj = {"action": action_type}
            
            # --- CASE A: Service Call (Complex conversion) ---
            if action_type == "call-service":
                raw_actions = call.data.get(ATTR_SERVICE_ACTION)
                
                if raw_actions and len(raw_actions) > 0:
                    first_action = raw_actions[0]
                    
                    # 1. Get Service Name (Handles new 'action' key or old 'service' key)
                    service_name = first_action.get("action") or first_action.get("service")
                    if service_name:
                        action_obj["service"] = service_name
                    
                    # 2. Merge 'target' and 'data' into 'service_data'
                    service_data = {}
                    
                    if "data" in first_action:
                        service_data.update(first_action["data"])
                    
                    if "target" in first_action:
                        # Flatten target (e.g., {'entity_id': 'light.bed'}) into service_data
                        service_data.update(first_action["target"])
                    
                    if service_data:
                        action_obj["service_data"] = service_data

            # --- CASE B: Navigation / URL ---
            elif action_type == "navigate":
                action_obj["navigation_path"] = call.data.get(ATTR_NAVIGATION_PATH)
            elif action_type == "url":
                action_obj["url_path"] = call.data.get(ATTR_NAVIGATION_PATH)
            
            new_msg["tap_action"] = action_obj
            
        elif ATTR_TAP_ACTION in call.data:
            # Legacy fallback
            new_msg["tap_action"] = call.data[ATTR_TAP_ACTION]

        # 4. Handle Confirmation override
        if ATTR_CONFIRM in call.data:
            new_msg["confirm"] = call.data[ATTR_CONFIRM]
        if ATTR_CONFIRM_MESSAGE in call.data:
            new_msg["confirm_message"] = call.data[ATTR_CONFIRM_MESSAGE]

        for sensor in get_targets(call):
            sensor.add_message(new_msg)

    def handle_dismiss(call: ServiceCall):
        msg_id = call.data[ATTR_ID]
        for sensor in get_targets(call):
            sensor.remove_message(msg_id)

    def handle_dismiss_all(call: ServiceCall):
        for sensor in get_targets(call):
            sensor.clear_all_messages()

    hass.services.async_register(DOMAIN, SERVICE_CREATE, handle_create, schema=CREATE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DISMISS, handle_dismiss, schema=DISMISS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DISMISS_ALL, handle_dismiss_all, schema=DISMISS_ALL_SCHEMA)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
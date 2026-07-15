"""The Detailed Hello World Push integration."""
import logging
from .const import CONF_HOST, CONF_SWITCHES, CONF_SENSORS

from . import hub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import CONF_PORT

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# List of platforms to support. There should be a matching .py file for each,
# eg <cover.py> and <sensor.py>
PLATFORMS = ["switch", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.
    
    host = entry.options.get(CONF_HOST)
    if host == None:
        host = entry.data.get(CONF_HOST)

    port = entry.options.get(CONF_PORT)
    if port == None:
        port = entry.data.get(CONF_PORT)
        
    _LOGGER.debug(f"async_setup_entry - host : {host}, port : {port}")

    hass.data[DOMAIN][entry.entry_id] = hub.Hub(hass, host, port)
    _LOGGER.debug(
        f"create sensor entity size : {entry.data.get(CONF_SENSORS)}")
    _LOGGER.debug(f"create switch entity size : {entry.data.get(CONF_SWITCHES)}")

    entry.async_on_unload(entry.add_update_listener(update_listener))
    # Forward the entry to all entity platforms and wait until setup completes.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    _LOGGER.debug("call async_unload_entry")
    hub = hass.data[DOMAIN][entry.entry_id]
    hub._unload = True
    hub.close()
    for listener in hass.data[DOMAIN]["listener"]:
        listener()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

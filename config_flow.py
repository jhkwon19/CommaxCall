"""Config flow for Hello World integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, Optional
from datetime import datetime
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry
import homeassistant.helpers.device_registry


from .const import CONF_BELL_START_PACKET, CONF_CALL_END_PACKET, CONF_SWITCH_OFF_PACKET, CONF_SWITCH_OFF_TIMER, CONF_SWITCHES, CONF_SENSORS, CONF_SWITCH_ON_PACKET
from .const import DOMAIN, CONF_NAME, NAME, CONF_ADD_ENTITY_TYPE, CONF_HOST, CONF_PORT, DEFAULT_PORT, CONF_BELL_START_PACKET, CONF_BELL_END_PACKET, CONF_BELL_OFF_TIMER, ENTITY_TYPES

from homeassistant import config_entries, exceptions
from homeassistant.core import callback

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass


_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello World."""

    VERSION = 1
    # Pick one of the available connection classes in homeassistant/config_entries.py
    # This tells HA if it should be asking for updates, or it'll be notified of updates
    # automatically. This example uses PUSH, as the dummy hub will notify HA of
    # changes.
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Handle the initial step."""
        # This goes through the steps to take the user through the setup process.
        # Using this it is possible to update the UI and prompt for additional
        # information. This example provides a single form (built from `DATA_SCHEMA`),
        # and when that has some validated input, it calls `async_create_entry` to
        # actually create the HA config entry. Note the "title" value is returned by
        # `validate_input` above.
        errors = {}
        if user_input is not None:
            # if user_input[CONF_NETWORK_SEARCH] == True:
            #    return self.async_create_entry(title=user_input[CONF_AREA_NAME], data=user_input)
            # else:
            self.data = user_input
            #self.data[CONF_SWITCHES] = []
            #self.data[CONF_SENSORS] = []
            # self.devices = await get_available_device()
            # return await self.async_step_hosts()
            return self.async_create_entry(title=NAME, data=self.data)

        # If there is no user input or there were errors, show the form again, including any errors that were found with the input.
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Handle a option flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self.data = None

    def _initialize_data(self) -> None:
        """Copy the current entry values after Home Assistant injects the entry."""
        if self.data is not None:
            return

        options = self.config_entry.options
        self.data = {
            CONF_HOST: options.get(
                CONF_HOST, self.config_entry.data[CONF_HOST]
            ),
            CONF_PORT: options.get(
                CONF_PORT, self.config_entry.data[CONF_PORT]
            ),
            CONF_SENSORS: list(options.get(CONF_SENSORS, [])),
            CONF_SWITCHES: list(options.get(CONF_SWITCHES, [])),
        }

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the options for the custom component."""
        self._initialize_data()
        errors: Dict[str, str] = {}

        all_entities_4_sensor = {}
        all_entities_4_switch = {}
        all_entities_by_id_4_sensor = {}
        all_entities_by_id_4_switch = {}

        entity_registry = homeassistant.helpers.entity_registry.async_get(self.hass)
        entities = homeassistant.helpers.entity_registry.async_entries_for_config_entry(entity_registry, self.config_entry.entry_id)

        device_registry = homeassistant.helpers.device_registry.async_get(self.hass)
        devices = homeassistant.helpers.device_registry.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id)

        # Default value for our multi-select.
        for host in self.data[CONF_SENSORS]:
            for e in entities:
                if e.original_device_class == BinarySensorDeviceClass.SOUND and e.original_name == host[CONF_NAME]:
                    
                    name = e.original_name

                    all_entities_4_sensor[e.entity_id] = '{} - {}'.format(
                        name, e.entity_id)

                    all_entities_by_id_4_sensor[(
                        host[CONF_NAME],
                        host[CONF_BELL_START_PACKET],
                        host[CONF_BELL_END_PACKET],
                        host[CONF_CALL_END_PACKET],
                        host[CONF_BELL_OFF_TIMER],
                    )] = e.entity_id
                    break

        for host in self.data[CONF_SWITCHES]:
            for e in entities:
                if e.original_device_class == SwitchDeviceClass.SWITCH and e.original_name == host[CONF_NAME]:
                    _LOGGER.debug(f"host is : {host}")
                    name = e.original_name

                    all_entities_4_switch[e.entity_id] = '{} - {}'.format(
                        name, e.entity_id)

                    all_entities_by_id_4_switch[(
                        host[CONF_NAME],
                        host[CONF_SWITCH_ON_PACKET],
                        host[CONF_SWITCH_OFF_PACKET],
                        host[CONF_SWITCH_OFF_TIMER],
                    )] = e.entity_id
                    break
        
        _LOGGER.debug(f"collect sensors : {all_entities_by_id_4_sensor}")
        _LOGGER.debug(f"collect switches : {all_entities_by_id_4_switch}")

        if user_input is not None:
            if not errors:
                self.data[CONF_HOST] = user_input[CONF_HOST]
                self.data[CONF_PORT] = user_input[CONF_PORT]
                self.data[CONF_SWITCHES].clear()
                self.data[CONF_SENSORS].clear()
                remove_entities = []

                _LOGGER.debug(f"all entities by 4 sensor : {all_entities_by_id_4_sensor}")
                for key in all_entities_by_id_4_sensor:
                    if all_entities_by_id_4_sensor[key] not in user_input[CONF_SENSORS]:
                        _LOGGER.debug("remove entity : %s", all_entities_by_id_4_sensor[key])
                        remove_entities.append(all_entities_by_id_4_sensor[key])
                        #self.config_entry.data[CONF_DEVICES].remove( { host[CONF_HOST], [e.name for e in devices if e.id == all_devices_by_host[host[CONF_HOST]]] })
                    else:
                        _LOGGER.debug("append entity : %s", all_entities_by_id_4_sensor[key])
                        self.data[CONF_SENSORS].append(
                            {
                                CONF_NAME: key[0],
                                CONF_BELL_START_PACKET: key[1],
                                CONF_BELL_END_PACKET: key[2],
                                CONF_CALL_END_PACKET: key[3],
                                CONF_BELL_OFF_TIMER: key[4],
                            }
                        )

                _LOGGER.debug(f"all entities by 4 switch : {all_entities_by_id_4_switch}")
                for key in all_entities_by_id_4_switch:
                    if all_entities_by_id_4_switch[key] not in user_input[CONF_SWITCHES]:
                        _LOGGER.debug("remove entity : %s",
                                      all_entities_by_id_4_switch[key])
                        remove_entities.append(
                            all_entities_by_id_4_switch[key])
                        #self.config_entry.data[CONF_DEVICES].remove( { host[CONF_HOST], [e.name for e in devices if e.id == all_devices_by_host[host[CONF_HOST]]] })
                    else:
                        _LOGGER.debug("append entity : %s", all_entities_by_id_4_switch[key])
                        self.data[CONF_SWITCHES].append(
                            {
                                CONF_NAME: key[0],
                                CONF_SWITCH_ON_PACKET: key[1],
                                CONF_SWITCH_OFF_PACKET: key[2],
                                CONF_SWITCH_OFF_TIMER: key[3],
                            }
                        )

                for id in remove_entities:
                    _LOGGER.debug(f"remove entity id - {id}")
                    entity_registry.async_remove(id)

                if user_input.get(CONF_ADD_ENTITY_TYPE) == "sensor":
                    # if len(self.devices) <= 0:
                    #    return self.async_create_entry(title=self.cnfig_entry.data[CONF_AREA_NAME], data=self.config_entry.data)
                    # else:
                    _LOGGER.debug("add sensor entity")
                    return await self.async_step_sensor()
                elif user_input.get(CONF_ADD_ENTITY_TYPE) == "switch":
                    _LOGGER.debug("add switch_entity")
                    return await self.async_step_switch()

                _LOGGER.debug(f"sensor size {len(self.data[CONF_SENSORS])}, switch size : {len(self.data[CONF_SWITCHES])}")
                if len(self.data[CONF_SENSORS]) + len(self.data[CONF_SWITCHES]) <= 0:
                    for d in devices:
                        device_registry.async_remove_device(d.id)

                # User is done adding repos, create the config entry.
                self.data["modifydatetime"] = str(datetime.now())
                return self.async_create_entry(title=NAME, data=self.data)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self.data[CONF_HOST]): cv.string,
                vol.Required(CONF_PORT, default=self.data[CONF_PORT]): cv.port,
                vol.Optional(CONF_SENSORS, default=list(all_entities_4_sensor)): cv.multi_select(all_entities_4_sensor),
                vol.Optional(CONF_SWITCHES, default=list(all_entities_4_switch)): cv.multi_select(all_entities_4_switch),
                vol.Optional(CONF_ADD_ENTITY_TYPE): vol.In(ENTITY_TYPES)
                #vol.Optional(CONF_USE_SETUP_MODE, False, cv.boolean),
                #vol.Optional(CONF_ADD_GROUP_DEVICE, False, cv.boolean),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

    async def async_step_sensor(self, user_input: Optional[Dict[str, Any]] = None):
        """Second step in config flow to add a repo to watch."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("async sensor entity user input is not none")
            if not errors:
                # Input is valid, set data.
                self.data[CONF_SENSORS].append(
                    {
                        CONF_NAME: user_input.get(CONF_NAME, CONF_NAME),
                        CONF_BELL_START_PACKET: user_input.get(CONF_BELL_START_PACKET),
                        CONF_BELL_END_PACKET: user_input.get(CONF_BELL_END_PACKET),
                        CONF_CALL_END_PACKET: user_input.get(CONF_CALL_END_PACKET),
                        CONF_BELL_OFF_TIMER: user_input.get(CONF_BELL_OFF_TIMER),
                    }
                )

                _LOGGER.debug("call async_create_entry")
                self.data["modifydatetime"] = str(datetime.now())
                return self.async_create_entry(title=NAME, data=self.data)

        return self.async_show_form(
            step_id="sensor",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_BELL_START_PACKET): cv.string,
                        vol.Required(CONF_BELL_END_PACKET): cv.string,
                        vol.Required(CONF_CALL_END_PACKET): cv.string,
                        vol.Required(CONF_BELL_OFF_TIMER): int,
                    }
            ), errors=errors
        )

    async def async_step_switch(self, user_input: Optional[Dict[str, Any]] = None):
        """Second step in config flow to add a repo to watch."""
        errors: Dict[str, str] = {}
        if user_input is not None:

            if not errors:
                # Input is valid, set data.
                self.data[CONF_SWITCHES].append(
                    {
                        CONF_NAME: user_input.get(CONF_NAME, CONF_NAME),
                        CONF_SWITCH_ON_PACKET: user_input.get(CONF_SWITCH_ON_PACKET),
                        CONF_SWITCH_OFF_PACKET: user_input.get(CONF_SWITCH_OFF_PACKET),
                        CONF_SWITCH_OFF_TIMER: user_input.get(CONF_SWITCH_OFF_TIMER),
                    }
                )
                _LOGGER.debug("call async_create_entry")
                self.data["modifydatetime"] = str(datetime.now())
                return self.async_create_entry(title=NAME, data=self.data)

        return self.async_show_form(
            step_id="switch",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_SWITCH_ON_PACKET): cv.string,
                        vol.Optional(CONF_SWITCH_OFF_PACKET): cv.string,
                        vol.Optional(CONF_SWITCH_OFF_TIMER): int,
                    }
            ), errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""

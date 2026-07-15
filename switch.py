"""Platform for sensor integration."""
# This file shows the setup for the sensors associated with the cover.
# They are setup in the same way with the call to the async_setup_entry function
# via HA from the module __init__. Each sensor has a device_class, this tells HA how
# to display it in the UI (for know types). The unit_of_measurement property tells HA
# what the unit is, so it can display the correct range. For predefined types (such as
# battery), the unit_of_measurement should match what's expected.
import logging
from threading import Timer
import threading
from xmlrpc.client import boolean
from typing import Optional
from homeassistant.const import (
    STATE_UNKNOWN, STATE_UNAVAILABLE,
)

from .device import Device
from .const import *
from homeassistant.helpers.entity import Entity, async_generate_entity_id, generate_entity_id
from homeassistant.helpers.event import async_track_state_change, track_state_change
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)


_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""

    hass.data[DOMAIN]["listener"] = []
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device = Device(NAME, config_entry)
    new_devices = []

    _LOGGER.debug(
        f"create switch entity size : {config_entry.options.get(CONF_SWITCHES)}")
    if config_entry.options.get(CONF_SWITCHES) != None:
        for entity in config_entry.options.get(CONF_SWITCHES):
            _LOGGER.debug("new_devices.append")
            new_devices.append(
                CommaxSwitch(
                    hass,
                    device,
                    hub,
                    entity[CONF_NAME],
                    entity[CONF_SWITCH_ON_PACKET],
                    entity[CONF_SWITCH_OFF_PACKET],
                    entity[CONF_SWITCH_OFF_TIMER],
                )
            )
    _LOGGER.debug("create switch entity2")
    if new_devices:
        async_add_devices(new_devices)
    _LOGGER.debug("create switch entity3")

class SwitchBase(SwitchEntity):
    """Base representation of a Hello World Sensor."""

    should_poll = False

    def __init__(self, device):
        """Initialize the sensor."""
        self._device = device

    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            # If desired, the name for the device could be different to the entity
            "name": self._device.name,
            "sw_version": self._device.firmware_version,
            "model": self._device.model,
            "manufacturer": self._device.manufacturer
        }

    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return True

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self._device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._device.remove_callback(self.async_write_ha_state)


class CommaxSwitch(SwitchBase):
    """Representation of a Thermal Comfort Sensor."""

    def __init__(self, hass, device, hub, entity_name, on_packet, off_packet, off_timer):
        """Initialize the sensor."""
        super().__init__(device)

        self.hass = hass
        self._hub = hub
        self._on_packet = None
        self._off_packet = None 
        self._on_packet = on_packet
        self._off_packet = off_packet
        self._off_timer = off_timer

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "{}_{}".format("commax_call", entity_name), hass=hass)

        hub._entities[CONF_SWITCHES][self.entity_id] = self

        self._name = "{}".format(entity_name)
        self._state = "off"
        self._attributes = {}
        self._attributes[CONF_SWITCH_OFF_PACKET] = off_packet
        self._attributes[CONF_SWITCH_ON_PACKET] = on_packet
        self._attributes[CONF_SWITCH_OFF_TIMER] = off_timer
        self._icon = None
        self._entity_picture = None

        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._device_class = SwitchDeviceClass.SWITCH
        self._unique_id = self.entity_id
        self._device = device

    def set_value(self, value: float) -> None:
        self._push_count = int(min(self._push_max, int(value)))
        _LOGGER.debug("call set value : %f", self._push_count)
        if int(self._push_count) != 0:
            if self._reset_timer != None:
                self._reset_timer.cancel()
            self._reset_timer = Timer(self._push_wait_time/1000, self.reset)
            self._reset_timer.start()

    def update(self):
        """Update the state."""

    def turn_on(self, **kargs):
        """turn the entity"""
        _LOGGER.debug(f"on packet : {self._on_packet}")
        if self._on_packet != None:
            self._hub.send_packet(self._on_packet)
        self._state = "on"
        self.schedule_update_ha_state(True)

        if self._off_timer != 0 and self._off_timer != None:
            threading.Timer(self._off_timer, self.turn_off).start()

    def turn_off(self, **kargs):
        """turn the entity"""
        _LOGGER.debug(f"off packet: {self._off_packet}")
        if self._off_packet != None:
            self._hub.send_packet(self._off_packet)
        self._state = "off"
        self.schedule_update_ha_state(True)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        # return self._state
        return self._state

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._unique_id is not None:
            return self._unique_id


def _is_valid_state(state) -> bool:
    return state and state.state != STATE_UNKNOWN and state.state != STATE_UNAVAILABLE

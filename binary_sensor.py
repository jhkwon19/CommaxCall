"""Platform for sensor integration."""
# This file shows the setup for the sensors associated with the cover.
# They are setup in the same way with the call to the async_setup_entry function
# via HA from the module __init__. Each sensor has a device_class, this tells HA how
# to display it in the UI (for know types). The unit_of_measurement property tells HA
# what the unit is, so it can display the correct range. For predefined types (such as
# battery), the unit_of_measurement should match what's expected.
import logging
from xmlrpc.client import boolean
from typing import Optional
from homeassistant.const import (
    STATE_UNKNOWN, STATE_UNAVAILABLE,
)
import threading

import asyncio

from homeassistant import components
from homeassistant import util
from homeassistant.helpers.entity import Entity

from .const import *
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id, generate_entity_id
from homeassistant.helpers.event import async_track_state_change, track_state_change

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

import math

_LOGGER = logging.getLogger(__name__)

# See cover.py for more details.
# Note how both entities for each roller sensor (battry and illuminance) are added at
# the same time to the same list. This way only a single async_add_devices call is
# required.

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""

    hass.data[DOMAIN]["listener"] = []

    hub = hass.data[DOMAIN][config_entry.entry_id]

    device = Device(NAME, config_entry)
    
    new_devices = []
    _LOGGER.debug(f"config_entry : {config_entry.options.get(CONF_SENSORS)}")
    if config_entry.options.get(CONF_SENSORS) != None:
        for entity in config_entry.options.get(CONF_SENSORS):
            new_devices.append(
                BellSensor(
                    hass,
                    hub,
                    device,
                    entity[CONF_NAME],
                    entity[CONF_BELL_START_PACKET],
                    entity[CONF_BELL_END_PACKET],
                    entity[CONF_CALL_END_PACKET],
                    entity[CONF_BELL_OFF_TIMER],
                )
            )
    if new_devices:
        async_add_devices(new_devices)


class Device:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(self, name, config):
        """Init dummy roller."""
        self._id = f"{name}_{config.entry_id}"
        self._name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        # Reports if the roller is moving up or down.
        # >0 is up, <0 is down. This very much just for demonstration.

        # Some static information about this device
        self.firmware_version = VERSION
        self.model = NAME
        self.manufacturer = NAME

    @property
    def name(self):
        return self._name
    @property
    def device_id(self):
        """Return ID for roller."""
        return self._id

    def register_callback(self, callback):
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

    def publish_updates(self):
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()

# This base class shows the common properties and methods for a sensor as used in this
# example. See each sensor for further details about properties and methods that
# have been overridden.


class SensorBase(BinarySensorEntity):
    """Base representation of a Hello World Sensor."""

    should_poll = False

    def __init__(self, device):
        """Initialize the sensor."""
        self._device = device

    # To link this entity to the cover device, this property must return an
    # identifiers value matching that used in the cover, but no other information such
    # as name. If name is returned, this entity will then also become a device in the
    # HA UI.
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


    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
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


class BellSensor(SensorBase):
    """Representation of a Thermal Comfort Sensor."""

    def __init__(self, hass, hub, device, entity_name, bell_start_packet, bell_end_packet, call_end_packet, bell_off_timer):
        """Initialize the sensor."""
        _LOGGER.debug("call init")
        super().__init__(device)

        self.hass = hass
        #self._switch_entity = switch_entity
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "{}_{}".format("commax_call", entity_name), hass=hass)
        
        hub.add_sensor(self)
        #hub._entities[CONF_SENSORS][self.entity_id] = self
        #_LOGGER.debug(
        #    f"add sensor entity size {len(hub._entities[CONF_SENSORS])}")

        self._bell_start_packet = bell_start_packet
        self._bell_end_packet = bell_end_packet
        self._call_end_packet = call_end_packet
        self._bell_off_timer = bell_off_timer
        self._timer = None
        self._attributes = {}
        self._attributes[CONF_BELL_START_PACKET] = bell_start_packet
        self._attributes[CONF_BELL_END_PACKET] = bell_end_packet
        self._attributes[CONF_CALL_END_PACKET] = call_end_packet
        self._attributes[CONF_BELL_OFF_TIMER] = bell_off_timer

        self._name = "{}".format(entity_name)
        self._value = False

        self._attr_device_class = BinarySensorDeviceClass.SOUND
        self._device_class = BinarySensorDeviceClass.SOUND
        self._unique_id = self.entity_id
        self._device = device


    def set_state(self, state):
        _LOGGER.debug(f"call set state : {state}")
        self._value = state
        self.schedule_update_ha_state(True)

    def on_recv_data(self, data):
        if bytearray.fromhex(self._bell_start_packet) == data:
            _LOGGER.debug("call start")
            self.set_state(True)
            if self._timer != None:
                self._timer.cancel()
            _LOGGER.debug(f"force off timer : {self._bell_off_timer}")
            self._timer = threading.Timer(
                self._bell_off_timer, self.bell_force_off)
            self._timer.start()
        elif bytearray.fromhex(self._bell_end_packet) == data or bytearray.fromhex(self._call_end_packet) == data:
            _LOGGER.debug("call end")
            self.set_state(False)

    def set_state(self, state):
        _LOGGER.debug(f"call set state : {state}")
        self._value = state
        self.schedule_update_ha_state(True)

    def update(self):
        """Update the state."""

    def bell_force_off(self):
        _LOGGER.debug("bell force off")
        self.set_state(False)


    """Sensor Properties"""
    @property
    def is_on(self):
        return self._value

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return self._attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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

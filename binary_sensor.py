"""패킷으로 상태가 바뀌는 벨 바이너리 센서 플랫폼입니다.

각 BellSensor는 수신한 16바이트 패킷을 설정된 시작 및 종료 패킷과 비교합니다.
상태는 Home Assistant로 즉시 전달되며 이 플랫폼은 주기적으로 폴링하지 않습니다.
"""
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

ENTITY_ID_FORMAT = "binary_sensor.{}"


async def async_setup_entry(hass, config_entry, async_add_devices):
    """이 Config Entry의 옵션에 저장된 모든 벨 센서를 생성합니다."""

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
    """같은 Config Entry의 벨 센서들이 공유하는 장치 정보입니다.

    현재 ``device.Device``와 같은 역할을 하며 기존 센서 플랫폼 구조와의
    호환성을 위해 이 파일에 유지하고 있습니다.
    """

    def __init__(self, name, config):
        """Home Assistant에 표시할 식별자와 장치 정보를 초기화합니다."""
        self._id = f"{name}_{config.entry_id}"
        self._name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        # 여러 엔티티를 하나의 HA 장치 페이지에 묶기 위한 고정 정보입니다.
        self.firmware_version = VERSION
        self.model = NAME
        self.manufacturer = NAME

    @property
    def name(self):
        return self._name
    @property
    def device_id(self):
        """엔티티의 device_info에서 사용할 식별자를 반환합니다."""
        return self._id

    def register_callback(self, callback):
        """Home Assistant 상태 갱신 콜백을 등록합니다."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """앞서 등록한 콜백을 제거합니다."""
        self._callbacks.discard(callback)

    def publish_updates(self):
        """등록된 모든 콜백을 호출합니다."""
        for callback in self._callbacks:
            callback()

class SensorBase(BinarySensorEntity):
    """Commax 벨 센서에 공통 장치 정보를 제공합니다."""

    should_poll = False

    def __init__(self, device):
        """센서의 공통 장치 정보를 초기화합니다."""
        self._device = device

    @property
    def device_info(self):
        """이 엔티티를 Config Entry의 Commax 장치 아래에 묶습니다."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            # 장치 이름과 엔티티 이름은 필요에 따라 서로 다르게 지정할 수 있습니다.
            "name": self._device.name,
            "sw_version": self._device.firmware_version,
            "model": self._device.model,
            "manufacturer": self._device.manufacturer
        }


    @property
    def available(self) -> bool:
        """엔티티 사용 가능 여부를 반환합니다. 현재는 항상 참입니다."""
        return True

    async def async_added_to_hass(self):
        """엔티티가 HA에 추가될 때 호출됩니다."""
        # 센서 상태가 바뀌면 HA에 알릴 수 있도록 콜백을 등록합니다.
        self._device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """엔티티가 HA에서 제거되기 전에 호출됩니다."""
        # async_added_to_hass에서 등록한 콜백을 해제합니다.
        self._device.remove_callback(self.async_write_ha_state)


class BellSensor(SensorBase):
    """설정된 호출 패킷에는 켜지고 종료 패킷에는 꺼지는 벨 센서입니다."""

    def __init__(self, hass, hub, device, entity_name, bell_start_packet, bell_end_packet, call_end_packet, bell_off_timer):
        """센서의 패킷 조건, 자동 종료 시간 및 초기 상태를 설정합니다."""
        _LOGGER.debug("call init")
        super().__init__(device)

        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "{}_{}".format("commax_call", entity_name), hass=hass)
        
        hub.add_sensor(self)

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
        # 기존 릴리스가 잘못된 commax_call 도메인으로 unique_id를 만들었으므로
        # 레지스트리, 자동화 및 대시보드 연결을 유지하기 위해 그 값은 보존합니다.
        self._unique_id = f"{DOMAIN}.{self.entity_id.split('.', 1)[1]}"
        self._device = device

    def on_recv_data(self, data):
        """Hub가 조립한 완전한 패킷 하나를 센서 상태에 반영합니다."""
        if bytearray.fromhex(self._bell_start_packet) == data:
            _LOGGER.debug("call start")
            self.set_state(True)
            if self._timer != None:
                self._timer.cancel()
            _LOGGER.debug(f"force off timer : {self._bell_off_timer}")
            self._timer = threading.Timer(
                self._bell_off_timer,
                lambda: self.hass.add_job(self.bell_force_off),
            )
            self._timer.daemon = True
            self._timer.start()
        elif bytearray.fromhex(self._bell_end_packet) == data or bytearray.fromhex(self._call_end_packet) == data:
            _LOGGER.debug("call end")
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self.set_state(False)

    def set_state(self, state):
        _LOGGER.debug(f"call set state : {state}")
        self._value = state
        self.schedule_update_ha_state(True)

    def update(self):
        """폴링용 상태 갱신 메서드입니다. 현재는 사용하지 않습니다."""

    def bell_force_off(self):
        """종료 패킷을 놓쳐도 벨이 계속 켜져 있지 않도록 강제로 끕니다."""
        _LOGGER.debug("bell force off")
        self._timer = None
        self.set_state(False)

    async def async_will_remove_from_hass(self):
        """강제 OFF 타이머를 취소하고 상태 콜백을 해제합니다."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        await super().async_will_remove_from_hass()


    """Home Assistant에 노출하는 센서 속성입니다."""
    @property
    def is_on(self):
        return self._value

    @property
    def extra_state_attributes(self):
        """이 엔티티에 설정된 패킷과 타이머 속성을 반환합니다."""
        return self._attributes

    @property
    def name(self):
        """센서 이름을 반환합니다."""
        return self._name

    @property
    def device_class(self) -> Optional[str]:
        """센서의 장치 클래스를 반환합니다."""
        return self._device_class
        
    @property
    def unique_id(self) -> str:
        """엔티티의 고유 ID를 반환합니다."""
        if self._unique_id is not None:
            return self._unique_id


def _is_valid_state(state) -> bool:
    return state and state.state != STATE_UNKNOWN and state.state != STATE_UNAVAILABLE

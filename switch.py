"""Hub를 통해 설정된 패킷을 전송하는 명령 스위치 플랫폼입니다."""
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

ENTITY_ID_FORMAT = "switch.{}"

async def async_setup_entry(hass, config_entry, async_add_devices):
    """이 Config Entry의 옵션에 저장된 모든 명령 스위치를 생성합니다."""

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
    """명령 스위치에 공통 Home Assistant 장치 정보를 제공합니다."""

    should_poll = False

    def __init__(self, device):
        """스위치의 공통 장치 정보를 초기화합니다."""
        self._device = device

    @property
    def device_info(self):
        """이 엔티티가 속한 장치 정보를 반환합니다."""
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
        # 스위치 상태가 바뀌면 HA에 알릴 수 있도록 콜백을 등록합니다.
        self._device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """엔티티가 HA에서 제거되기 전에 호출됩니다."""
        # async_added_to_hass에서 등록한 콜백을 해제합니다.
        self._device.remove_callback(self.async_write_ha_state)


class CommaxSwitch(SwitchBase):
    """Home Assistant가 스위치 상태를 바꾸면 설정된 패킷을 전송합니다."""

    def __init__(self, hass, device, hub, entity_name, on_packet, off_packet, off_timer):
        """패킷 설정을 저장하고 이 스위치를 공유 Hub에 등록합니다."""
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
        # 기존 릴리스가 잘못된 commax_call 도메인으로 unique_id를 만들었으므로
        # 레지스트리, 자동화 및 대시보드 연결을 유지하기 위해 그 값은 보존합니다.
        self._unique_id = f"{DOMAIN}.{self.entity_id.split('.', 1)[1]}"
        self._device = device
        self._off_timer_handle = None

    def set_value(self, value: float) -> None:
        self._push_count = int(min(self._push_max, int(value)))
        _LOGGER.debug("call set value : %f", self._push_count)
        if int(self._push_count) != 0:
            if self._reset_timer != None:
                self._reset_timer.cancel()
            self._reset_timer = Timer(self._push_wait_time/1000, self.reset)
            self._reset_timer.start()

    def update(self):
        """폴링용 상태 갱신 메서드입니다. 현재는 사용하지 않습니다."""

    def turn_on(self, **kargs):
        """ON 패킷을 보내고 필요한 경우 자동 OFF를 예약합니다."""
        _LOGGER.debug(f"on packet : {self._on_packet}")
        if self._on_packet != None:
            self._hub.send_packet(self._on_packet)
        self._state = "on"
        self.schedule_update_ha_state(True)

        if self._off_timer != 0 and self._off_timer != None:
            if self._off_timer_handle is not None:
                self._off_timer_handle.cancel()
            self._off_timer_handle = threading.Timer(
                self._off_timer,
                lambda: self.hass.add_job(self.turn_off),
            )
            self._off_timer_handle.daemon = True
            self._off_timer_handle.start()

    def turn_off(self, **kargs):
        """OFF 패킷을 보내고 꺼짐 상태를 Home Assistant에 반영합니다."""
        _LOGGER.debug(f"off packet: {self._off_packet}")
        if self._off_packet != None:
            self._hub.send_packet(self._off_packet)
        self._state = "off"
        self.schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self):
        """자동 OFF 타이머를 취소하고 상태 콜백을 해제합니다."""
        if self._off_timer_handle is not None:
            self._off_timer_handle.cancel()
            self._off_timer_handle = None
        await super().async_will_remove_from_hass()

    async def async_toggle(self, **kwargs):
        """스위치 상태를 전환합니다. 현재 별도 동작은 구현하지 않았습니다."""

    @property
    def extra_state_attributes(self):
        """이 엔티티에 설정된 패킷과 타이머 속성을 반환합니다."""
        return self._attributes

    @property
    def name(self):
        """스위치 이름을 반환합니다."""
        return self._name

    @property
    def state(self):
        """현재 스위치 상태를 반환합니다."""
        return self._state

    @property
    def device_class(self) -> Optional[str]:
        """스위치의 장치 클래스를 반환합니다."""
        return self._device_class

    @property
    def unique_id(self) -> str:
        """엔티티의 고유 ID를 반환합니다."""
        if self._unique_id is not None:
            return self._unique_id


def _is_valid_state(state) -> bool:
    return state and state.state != STATE_UNKNOWN and state.state != STATE_UNAVAILABLE

"""EW11 접속 정보와 Commax 엔티티 패킷을 입력하는 UI 설정 흐름입니다.

최초 설정에서는 TCP 접속 정보만 저장합니다. 이후 옵션 설정에서 각 패킷을
포함한 벨 센서와 스위치 목록을 관리합니다. 옵션을 저장하면 ``__init__.py``의
리스너를 통해 Config Entry를 다시 로딩합니다.
"""
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
    """통합 구성요소를 처음 추가할 때 EW11 호스트와 포트를 입력받습니다."""

    VERSION = 1
    # 엔티티 상태는 HA의 주기적인 폴링이 아니라 소켓 수신 데이터로 변경됩니다.
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """접속 정보 입력 화면을 표시하고 최초 Config Entry를 생성합니다."""
        errors = {}
        if user_input is not None:
            self.data = user_input
            return self.async_create_entry(title=NAME, data=self.data)

        # 아직 입력이 없거나 오류가 있으면 오류 정보와 함께 입력 화면을 다시 표시합니다.
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
        """통합 구성요소의 '구성' 버튼에서 사용할 옵션 흐름을 반환합니다."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """패킷 기반 센서와 스위치를 추가·유지·삭제합니다."""

    def __init__(self) -> None:
        """옵션 설정 흐름을 초기화합니다."""
        self.data = None

    def _initialize_data(self) -> None:
        """현재 설정값을 옵션 흐름에서 수정할 작업 데이터로 한 번만 복사합니다."""
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
        """커스텀 통합 구성요소의 옵션을 관리합니다."""
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

        # 저장된 패킷 정의와 Home Assistant 레지스트리에 존재하는 엔티티를
        # 연결하여 다중 선택 항목을 다시 구성합니다.
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
                # 선택된 엔티티는 옵션에 다시 저장하고, 선택 해제된 엔티티는
                # 아래에서 엔티티 레지스트리로부터 제거합니다.
                for key in all_entities_by_id_4_sensor:
                    if all_entities_by_id_4_sensor[key] not in user_input[CONF_SENSORS]:
                        _LOGGER.debug("remove entity : %s", all_entities_by_id_4_sensor[key])
                        remove_entities.append(all_entities_by_id_4_sensor[key])
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
                    _LOGGER.debug("add sensor entity")
                    return await self.async_step_sensor()
                elif user_input.get(CONF_ADD_ENTITY_TYPE) == "switch":
                    _LOGGER.debug("add switch_entity")
                    return await self.async_step_switch()

                _LOGGER.debug(f"sensor size {len(self.data[CONF_SENSORS])}, switch size : {len(self.data[CONF_SWITCHES])}")
                if len(self.data[CONF_SENSORS]) + len(self.data[CONF_SWITCHES]) <= 0:
                    for d in devices:
                        device_registry.async_remove_device(d.id)

                # 추가 단계가 선택되지 않았으므로 수정된 옵션을 바로 저장합니다.
                self.data["modifydatetime"] = str(datetime.now())
                return self.async_create_entry(title=NAME, data=self.data)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self.data[CONF_HOST]): cv.string,
                vol.Required(CONF_PORT, default=self.data[CONF_PORT]): cv.port,
                vol.Optional(CONF_SENSORS, default=list(all_entities_4_sensor)): cv.multi_select(all_entities_4_sensor),
                vol.Optional(CONF_SWITCHES, default=list(all_entities_4_switch)): cv.multi_select(all_entities_4_switch),
                vol.Optional(CONF_ADD_ENTITY_TYPE): vol.In(ENTITY_TYPES)
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

    async def async_step_sensor(self, user_input: Optional[Dict[str, Any]] = None):
        """벨 센서 하나의 패킷 서명과 자동 종료 시간을 입력받습니다."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("async sensor entity user input is not none")
            if not errors:
                # 입력값을 센서 설정 목록에 추가합니다.
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
        """스위치 하나의 송신 패킷과 자동 꺼짐 시간을 입력받습니다."""
        errors: Dict[str, str] = {}
        if user_input is not None:

            if not errors:
                # 입력값을 스위치 설정 목록에 추가합니다.
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
    """장치에 연결할 수 없음을 나타내는 오류입니다."""


class InvalidHost(exceptions.HomeAssistantError):
    """호스트 이름이 올바르지 않음을 나타내는 오류입니다."""

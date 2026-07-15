"""Commax Call 통합 구성요소의 Home Assistant 진입점입니다.

Config Entry마다 하나의 :class:`Hub` 수명 주기를 관리하고, Hub를 사용하는
스위치와 바이너리 센서 플랫폼을 Home Assistant에 로딩하도록 요청합니다.
"""
import logging
from .const import CONF_HOST, CONF_SWITCHES, CONF_SENSORS

from . import hub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import CONF_PORT

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# 각 이름은 Config Entry마다 로딩할 플랫폼 모듈에 대응합니다.
PLATFORMS = ["switch", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Home Assistant 런타임 데이터에 통합 구성요소 전용 공간을 만듭니다."""
    # 실행 중에만 필요한 객체는 hass.data에 저장합니다. 영구 사용자 설정은
    # ConfigEntry에 저장되며 config_flow.py에서 관리합니다.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정된 EW11 접속 지점 하나에 대한 TCP Hub와 엔티티를 생성합니다."""
    
    host = entry.options.get(CONF_HOST)
    if host == None:
        host = entry.data.get(CONF_HOST)

    port = entry.options.get(CONF_PORT)
    if port == None:
        port = entry.data.get(CONF_PORT)
        
    _LOGGER.debug(f"async_setup_entry - host : {host}, port : {port}")

    # 각 플랫폼 모듈은 entry_id로 이 Hub 인스턴스를 찾아 공유합니다.
    hass.data[DOMAIN][entry.entry_id] = hub.Hub(hass, host, port)
    _LOGGER.debug(
        f"create sensor entity size : {entry.data.get(CONF_SENSORS)}")
    _LOGGER.debug(f"create switch entity size : {entry.data.get(CONF_SWITCHES)}")

    entry.async_on_unload(entry.add_update_listener(update_listener))
    # Config Entry를 모든 엔티티 플랫폼으로 전달하고 설정 완료를 기다립니다.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def update_listener(hass, entry):
    """사용자가 옵션을 저장하면 관련 런타임 객체를 모두 다시 로딩합니다."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Config Entry의 통신을 중단하고 모든 엔티티를 언로드합니다."""
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

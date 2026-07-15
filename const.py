"""Commax Call에서 공유하는 상수와 영구 Config Entry 키입니다."""

# DOMAIN은 manifest.json 및 custom_components 하위 디렉터리 이름과 일치해야 합니다.
DOMAIN = "commax_call"
NAME = "Commax Call"
VERSION = "1.0.0"

# 옵션 화면에서 추가할 엔티티 종류를 선택할 때 표시하는 값입니다.
ENTITY_TYPES = {
    "sensor": ("bell"),
    "switch": ("switch"),
}

# EW11 TCP 서버 접속 설정입니다.
CONF_HOST, DEFAULT_HOST = "host", "192.168.11.2"
CONF_PORT, DEFAULT_PORT = "port", 8899

# 다음 문자열은 Home Assistant의 Config Entry에 영구 저장되는 키입니다.
CONF_SWITCHES = "switches"
CONF_SENSORS = "sensors"
CONF_ADD_ANODHER = "add_another"
CONF_NAME = "name"
CONF_ADD_ENTITY_TYPE = "add_entity_type"

CONF_BELL_START_PACKET = "bell_start_packet"
CONF_BELL_END_PACKET = "bell_end_packet"
CONF_SWITCH_ON_PACKET = "switch_on_packet"
CONF_SWITCH_OFF_PACKET = "switch_off_packet"
CONF_CALL_END_PACKET = "call_end_packet"
CONF_BELL_OFF_TIMER = "bell_off_timer"
CONF_SWITCH_OFF_TIMER = "switch_off_timer"

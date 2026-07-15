# This is the internal name of the integration, it should also match the directory
# name for the integration.
DOMAIN = "commax_call"
NAME = "Commax Call"
VERSION = "1.0.0"

ENTITY_TYPES = {
    "sensor": ("bell"),
    "switch": ("switch"),
}

CONF_HOST, DEFAULT_HOST = "host", "192.168.11.2"
CONF_PORT, DEFAULT_PORT = "port", 8899

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

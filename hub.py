import asyncio
import logging
import threading
import time
import socket

from .const import CONF_SENSORS, CONF_SWITCHES
from .const import VERSION, NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PACKET_LENGTH = 16
PACKET_START = 0x02
PACKET_END = 0x03
RECONNECT_DELAY = 10
CONNECT_TIMEOUT = 10


class Hub:
    """Dummy hub for Hello World example."""
    manufacturer = DOMAIN
    
    def __init__(self, hass, host, port):
        """Init dummy hub."""
        _LOGGER.debug("init hub")
        self.hass = hass
        self._host = host
        self._port = port
        self._timer = None
        self._entities = {}
        self._entities[CONF_SENSORS] = {}
        self._entities[CONF_SWITCHES] = {}
        self.online = True
        self._socket = None
        self._socket_lock = threading.Lock()
        self._recv_thread = None
        self._recv_buffer = bytearray()
        self._unload = False
        _LOGGER.debug("start server!!!")
        self._recv_thread = threading.Thread(target=self.start_server)
        self._recv_thread.daemon = True
        self._recv_thread.start()

    def add_sensor(self, entity):
        self._entities[CONF_SENSORS][entity.entity_id] = entity
        _LOGGER.debug(f"add sensor size {len(self._entities[CONF_SENSORS])}")

    def close(self):
        """Close the socket, including sockets already reset by the peer."""
        with self._socket_lock:
            sock = self._socket
            self._socket = None

        self.online = False
        if sock is None:
            return

        _LOGGER.debug("socket close")
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            # A peer reset or a failed connection leaves a socket that cannot
            # be shut down, but it still needs to be closed.
            pass
        finally:
            sock.close()

    def connect(self):
        """Connect to the EW11, retrying with a fresh socket each time."""
        self.close()

        while not self._unload:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT)
            try:
                _LOGGER.debug(
                    "try connect - IP: %s, port: %s", self._host, self._port
                )
                sock.connect((self._host, self._port))
            except OSError as err:
                sock.close()
                _LOGGER.warning(
                    "연결 실패 (%s), %s초 후 재연결 시도",
                    err,
                    RECONNECT_DELAY,
                )
                time.sleep(RECONNECT_DELAY)
                continue

            sock.settimeout(None)
            with self._socket_lock:
                if self._unload:
                    sock.close()
                    return False
                self._socket = sock
            self.online = True
            _LOGGER.info("EW11 연결 성공 - IP: %s, port: %s", self._host, self._port)
            return True

        return False
        
    def start_server(self):
        #str = "02 10 02 02 09 03 02 02 09 03 10 00 00 00 40 03"
        #num = bytearray.fromhex(str)
        #_LOGGER.debug(f"hex data test : {num}")
        if not self.connect():
            return

        while not self._unload:
            try:
                with self._socket_lock:
                    sock = self._socket
                if sock is None:
                    if not self.connect():
                        return
                    continue

                data = sock.recv(1024)
                if self._unload:
                    return
                if not data:
                    raise ConnectionResetError("EW11 closed the connection")

                _LOGGER.debug("recv data original: %s", data.hex(" "))
                for packet in self._extract_packets(data):
                    _LOGGER.debug("recv packet: %s", packet.hex(" "))
                    for entity in tuple(self._entities[CONF_SENSORS].values()):
                        _LOGGER.debug(
                            "entity id: %s, start packet: %s, end packet: %s",
                            entity.entity_id,
                            entity._bell_start_packet,
                            entity._bell_end_packet,
                        )
                        entity.on_recv_data(packet)
            except OSError as err:
                self._recv_buffer.clear()
                if self._unload:
                    return
                _LOGGER.warning("EW11 연결 끊김 (%s), 재연결합니다", err)
                if not self.connect():
                    return

    def _extract_packets(self, data):
        """Reassemble fixed-length packets from the TCP byte stream."""
        self._recv_buffer.extend(data)
        packets = []

        while self._recv_buffer:
            try:
                start = self._recv_buffer.index(PACKET_START)
            except ValueError:
                self._recv_buffer.clear()
                break

            if start:
                del self._recv_buffer[:start]

            if len(self._recv_buffer) < PACKET_LENGTH:
                break

            if self._recv_buffer[PACKET_LENGTH - 1] != PACKET_END:
                _LOGGER.debug(
                    "discard malformed packet prefix: %s",
                    self._recv_buffer[:PACKET_LENGTH].hex(" "),
                )
                del self._recv_buffer[0]
                continue

            packets.append(bytes(self._recv_buffer[:PACKET_LENGTH]))
            del self._recv_buffer[:PACKET_LENGTH]

        return packets

    def send_packet(self, data):
        """Send an entire packet or packet sequence to the EW11."""
        payload = bytes.fromhex(data)
        if not payload:
            return

        _LOGGER.debug("send packet: %s", payload.hex(" "))
        with self._socket_lock:
            sock = self._socket
            if sock is None:
                raise ConnectionError("EW11 is not connected")
            sock.sendall(payload)

    @property
    def hub_id(self):
        """ID for dummy hub."""
        return self._id

    async def test_connection(self):
        """Test connectivity to the Dummy hub is OK."""
        await asyncio.sleep(1)
        return True

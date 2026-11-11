"""Home Assistant 엔티티와 EW11 게이트웨이 사이의 TCP 통신을 담당합니다.

TCP는 바이트 스트림이므로 수신한 데이터 조각을 누적한 후 고정 길이의
Commax 패킷으로 다시 조립하여 벨 센서에 전달합니다.
"""

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
    """EW11 연결 하나를 유지하고 패킷을 통합 구성요소 엔티티로 전달합니다."""
    manufacturer = DOMAIN
    
    def __init__(self, hass, host, port):
        """엔티티 저장소를 초기화하고 백그라운드 수신 루프를 시작합니다."""
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
        # 블로킹 소켓 I/O가 Home Assistant의 asyncio 루프를 막지 않도록
        # 별도의 데몬 스레드에서 실행합니다.
        self._recv_thread = threading.Thread(target=self.start_server)
        self._recv_thread.daemon = True
        self._recv_thread.start()

    def add_sensor(self, entity):
        """수신 패킷을 검사할 벨 센서를 등록합니다."""
        self._entities[CONF_SENSORS][entity.entity_id] = entity
        _LOGGER.debug(f"add sensor size {len(self._entities[CONF_SENSORS])}")

    def close(self):
        """상대방이 이미 초기화한 경우를 포함하여 소켓을 안전하게 닫습니다."""
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
            # 상대방의 연결 초기화나 접속 실패 후에는 shutdown할 수 없더라도
            # 소켓 자체는 반드시 닫아야 합니다.
            pass
        finally:
            sock.close()

    def connect(self):
        """매 시도마다 새 소켓을 만들며 EW11에 연결될 때까지 재시도합니다."""
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
        """언로드될 때까지 패킷을 수신하고 소켓 오류가 나면 재연결합니다."""
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
                # recv()는 패킷 일부만 반환하거나 여러 패킷을 한꺼번에 반환할 수 있습니다.
                for packet in self._extract_packets(data):
                    _LOGGER.debug("recv packet: %s", packet.hex(" "))
                    for entity in tuple(self._entities[CONF_SENSORS].values()):
                        _LOGGER.debug(
                            "entity id: %s, start packet: %s, end packet: %s",
                            entity.entity_id,
                            entity._bell_start_packet,
                            entity._bell_end_packet,
                        )
                        # recv 루프는 별도 스레드에서 실행되므로 엔티티 상태 변경은
                        # Home Assistant 이벤트 루프로 전달합니다.
                        self.hass.add_job(entity.on_recv_data, packet)
            except OSError as err:
                self._recv_buffer.clear()
                if self._unload:
                    return
                _LOGGER.warning("EW11 연결 끊김 (%s), 재연결합니다", err)
                if not self.connect():
                    return

    def _extract_packets(self, data):
        """TCP 바이트 스트림에서 고정 길이 패킷을 다시 조립합니다."""
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
        """완전한 패킷 또는 연속된 패킷을 EW11로 전송합니다."""
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
        """호출 측에서 지정한 Hub 식별자를 반환합니다."""
        return self._id

    async def test_connection(self):
        """향후 설정 유효성 검사에서 사용할 Hub 연결 상태를 반환합니다."""
        await asyncio.sleep(1)
        return True

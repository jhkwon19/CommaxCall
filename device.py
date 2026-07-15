"""공유 Home Assistant 장치 정보와 상태 콜백 저장소입니다."""

import asyncio
from .const import NAME, VERSION

class Device:
    """Commax 엔티티를 Home Assistant의 논리 장치 하나로 묶습니다."""

    def __init__(self, name, config):
        """Config Entry ID를 사용하여 변하지 않는 장치 식별자를 만듭니다."""
        self._id = f"{name}_{config.entry_id}"
        self._name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self.firmware_version = VERSION
        self.model = NAME
        self.manufacturer = NAME

    @property
    def device_id(self):
        """엔티티의 ``device_info`` 속성에서 사용할 식별자를 반환합니다."""
        return self._id

    @property
    def name(self):
        return self._name

    def register_callback(self, callback):
        """Home Assistant 상태 갱신 콜백을 등록합니다."""
        self._callbacks.add(callback)

    def remove_callback(self, callback):
        """앞서 등록한 콜백을 제거합니다."""
        self._callbacks.discard(callback)

    async def publish_updates(self):
        """등록된 모든 콜백을 호출합니다."""
        for callback in self._callbacks:
            callback()

    def publish_updates(self):
        """등록된 모든 상태 갱신 콜백을 호출합니다."""
        for callback in self._callbacks:
            callback()

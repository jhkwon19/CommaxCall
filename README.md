# Commax Call

Commax 월패드 통신 패킷을 EW11 TCP 게이트웨이를 통해 송수신하고, 이를 Home Assistant의 벨 바이너리 센서와 스위치로 노출하는 커스텀 통합 구성요소입니다.

> 이 프로젝트는 특정 Commax/EW11 환경에서 관찰한 패킷을 사용합니다. 장치 모델이나 배선 환경에 따라 패킷 값이 다를 수 있으므로, 실제 장치에서 확인한 16바이트 HEX 패킷을 옵션에 입력해야 합니다.

## 전체 구조

```text
Home Assistant
├─ config_flow.py        연결 정보와 엔티티별 패킷을 UI에서 설정
├─ __init__.py           통합 구성요소 시작/종료 및 플랫폼 로딩
├─ hub.py                EW11 TCP 연결, 수신 패킷 조립, 송신 담당
├─ binary_sensor.py      수신 패킷을 벨의 ON/OFF 상태로 변환
├─ switch.py             스위치 조작을 HEX 패킷 송신으로 변환
├─ device.py             여러 엔티티를 하나의 HA 장치로 묶는 메타데이터
├─ const.py              도메인, 설정 키, 기본값
├─ manifest.json         Home Assistant 통합 구성요소 메타데이터
└─ translations/         설정 UI의 한국어/영어 문구
```

핵심 객체 관계는 다음과 같습니다.

```text
ConfigEntry (사용자 설정)
        │
        ▼
Hub ───────── TCP ───────── EW11 ───── Commax 월패드 통신선
 │                              
 ├─ BellSensor[]  ◀── 수신한 16바이트 패킷 비교
 │
 └─ CommaxSwitch[] ── 설정된 HEX 패킷 송신
```

## 실행 흐름

### 1. 통합 구성요소 등록

사용자가 Home Assistant UI에서 IP와 포트를 입력하면 `config_flow.py`가 Config Entry를 만듭니다. 기본 포트는 `8899`입니다.

### 2. Hub 생성과 플랫폼 로딩

`__init__.py`의 `async_setup_entry()`가 다음 작업을 수행합니다.

1. 해당 Config Entry의 host/port를 읽습니다.
2. `Hub` 인스턴스를 `hass.data[DOMAIN][entry_id]`에 저장합니다.
3. `switch`와 `binary_sensor` 플랫폼을 로딩합니다.
4. 옵션이 바뀌면 Config Entry 전체를 다시 로딩하도록 리스너를 등록합니다.

### 3. TCP 연결과 패킷 수신

`Hub`는 별도 데몬 스레드에서 EW11에 TCP 연결을 시도합니다. 연결이 끊어지면 10초 간격으로 다시 연결합니다.

TCP는 메시지 경계를 보존하지 않기 때문에 한 번의 `recv()`가 정확히 한 패킷이라는 보장이 없습니다. `Hub._extract_packets()`는 수신 데이터를 버퍼에 누적한 뒤 다음 조건에 맞는 패킷만 추출합니다.

- 길이: 16바이트
- 시작 바이트: `0x02`
- 종료 바이트: `0x03`

완성된 패킷은 등록된 모든 `BellSensor`의 `on_recv_data()`로 전달됩니다.

### 4. 벨 센서 상태 변경

각 `BellSensor`에는 세 종류의 패킷과 자동 종료 시간이 저장됩니다.

- `bell_start_packet`: 수신하면 센서를 ON으로 변경
- `bell_end_packet`: 수신하면 센서를 OFF로 변경
- `call_end_packet`: 수신하면 센서를 OFF로 변경
- `bell_off_timer`: 종료 패킷을 받지 못한 경우 지정 시간 후 강제로 OFF

센서마다 패킷을 따로 설정할 수 있으므로 공동현관 호출과 세대현관 호출처럼 서로 다른 패킷을 별도 엔티티로 만들 수 있습니다.

### 5. 스위치 패킷 송신

사용자가 `CommaxSwitch`를 켜거나 끄면 설정된 HEX 문자열을 바이트로 변환해 `Hub.send_packet()`으로 전송합니다.

- `switch_on_packet`: 스위치를 켤 때 전송
- `switch_off_packet`: 스위치를 끌 때 전송
- `switch_off_timer`: 0보다 크면 스위치를 켠 뒤 지정 시간 후 자동으로 끔

자동 OFF 시 `switch_off_packet`도 전송되므로 순간 동작 버튼처럼 사용할 수 있습니다.

## 설정 데이터

초기 설정의 IP와 포트는 `config_entry.data`에 저장되고, 통합 구성요소 옵션 화면에서 변경한 값과 센서/스위치 목록은 `config_entry.options`에 저장됩니다.

대략적인 형태는 다음과 같습니다.

```python
{
    "host": "192.168.11.2",
    "port": 8899,
    "sensors": [
        {
            "name": "공동현관 호출",
            "bell_start_packet": "02 ... 03",
            "bell_end_packet": "02 ... 03",
            "call_end_packet": "02 ... 03",
            "bell_off_timer": 30,
        }
    ],
    "switches": [
        {
            "name": "문 열기",
            "switch_on_packet": "02 ... 03",
            "switch_off_packet": "02 ... 03",
            "switch_off_timer": 1,
        }
    ],
}
```

`02 ... 03`은 설명을 위한 축약 표현입니다. 실제 설정에는 공백으로 구분된 전체 HEX 바이트를 입력해야 합니다.

## 설치 위치

Home Assistant 설정 디렉터리 아래에 다음 구조로 배치합니다.

```text
config/
└─ custom_components/
   └─ commax_call/
      ├─ __init__.py
      ├─ manifest.json
      └─ ...
```

파일을 배치한 후 Home Assistant를 재시작하고, **설정 → 기기 및 서비스 → 통합 구성요소 추가**에서 `Commax Call`을 선택합니다.

## 코드를 수정할 때 확인할 부분

- `hub.py`의 소켓 수신은 Home Assistant 이벤트 루프가 아닌 별도 스레드에서 실행됩니다.
- TCP 수신 단위와 Commax 패킷 단위는 다를 수 있으므로 `_extract_packets()`의 버퍼 조립 과정은 유지해야 합니다.
- 현재 프로토콜은 모든 패킷이 16바이트이고 `0x02`/`0x03`으로 시작/종료한다고 가정합니다.
- 설정 키 문자열은 여러 파일과 기존 Config Entry에서 함께 사용하므로 변경 시 마이그레이션이 필요합니다.
- 옵션 저장 후 `update_listener()`가 통합 구성요소를 다시 로딩하여 엔티티 구성을 반영합니다.
- 타이머 콜백과 수신 콜백은 다른 스레드에서 실행될 수 있으므로 Home Assistant 상태 갱신 방식을 수정할 때 스레드 안전성을 확인해야 합니다.

## 디버그 로그

Home Assistant의 `configuration.yaml`에 다음 설정을 추가하면 연결, 수신 및 송신 패킷 로그를 확인할 수 있습니다.

```yaml
logger:
  default: info
  logs:
    custom_components.commax_call: debug
```

로그에는 EW11의 IP 주소와 통신 패킷이 포함될 수 있으므로 외부에 공유하기 전에 내용을 확인하세요.


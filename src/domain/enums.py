"""Enumerations for Controller Node."""

from enum import Enum, auto


class ControlAction(Enum):
    """Control actions for the device."""

    NONE = "none"
    INFLATE = "inflate"
    DEFLATE = "deflate"


class ConnectionState(Enum):
    """Connection state for master node and serial device."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class DeviceZone(Enum):
    """Device zones using quadrant system.

    Zone mapping (quadrant-based):
    - Zone 1: 1사분면 (우측 상단 / Right Upper)
    - Zone 2: 2사분면 (좌측 상단 / Left Upper)
    - Zone 3: 3사분면 (좌측 하단 / Left Lower)
    - Zone 4: 4사분면 (우측 하단 / Right Lower)
    """

    ZONE_1 = 1  # 1사분면 (우측 상단)
    ZONE_2 = 2  # 2사분면 (좌측 상단)
    ZONE_3 = 3  # 3사분면 (좌측 하단)
    ZONE_4 = 4  # 4사분면 (우측 하단)


class PostureType(Enum):
    """자세 유형."""

    SUPINE = "supine"  # 앙와위 (바로 누운 자세)
    PRONE = "prone"  # 복와위 (엎드린 자세)
    LEFT_LATERAL = "left_lateral"  # 좌측와위 (왼쪽으로 누운 자세)
    RIGHT_LATERAL = "right_lateral"  # 우측와위 (오른쪽으로 누운 자세)
    SITTING = "sitting"  # 좌위 (앉은 자세)
    UNKNOWN = "unknown"  # 알 수 없음

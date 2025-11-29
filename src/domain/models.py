"""Domain models for Controller Node."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from typing_extensions import deprecated

from .enums import ControlAction, ConnectionState, DeviceZone, PostureType


@dataclass
class ControlSignal:
    """Control signal received from master node.

    This matches the format sent by master_node's ControlSender.
    """

    target_zones: List[int]
    action: ControlAction
    intensity: int  # 0-100

    @classmethod
    def from_dict(cls, data: dict) -> "ControlSignal":
        """Create ControlSignal from dictionary (JSON deserialization)."""
        return cls(
            target_zones=data.get("target_zones", []),
            action=ControlAction(data.get("action", "none")),
            intensity=data.get("intensity", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "target_zones": self.target_zones,
            "action": self.action.value,
            "intensity": self.intensity,
        }


@dataclass
class DeviceCommand:
    """Command to be sent to the physical device via serial.

    This is the internal representation that will be converted
    to the appropriate serial protocol. 압력은 on/off만 지원.
    """

    zone: DeviceZone
    action: ControlAction  # inflate = on, deflate = off
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"Zone {self.zone.value}: {self.action.value}"


@dataclass
class DeviceStatus:
    """Current status of the physical device."""

    zone_states: dict  # zone_id -> current state (e.g., pressure level)
    is_operational: bool
    last_command_success: bool
    error_message: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class SystemStatus:
    """Overall system status for display."""

    device_id: int
    master_connection: ConnectionState
    serial_connection: ConnectionState
    last_signal_received: Optional[datetime] = None
    last_command_executed: Optional[datetime] = None
    commands_executed: int = 0
    errors_count: int = 0


@dataclass
class ControlPacket:
    """마스터 노드에서 전송되는 통합 패킷."""

    posture: PostureType
    pressures: dict  # BodyPart.value -> 압력값
    durations: dict  # BodyPart.value -> 지속시간(초)
    controls: Optional[dict] = None  # 서버에서 받은 제어 명령 (nullable)

    @classmethod
    def from_dict(cls, data: dict) -> "ControlPacket":
        """딕셔너리에서 ControlPacket 생성."""
        posture_value = data.get("posture", "unknown")
        try:
            posture = PostureType(posture_value)
        except ValueError:
            posture = PostureType.UNKNOWN

        return cls(
            posture=posture,
            pressures=data.get("pressures", {}),
            durations=data.get("durations", {}),
            controls=data.get("controls"),
        )

    def to_dict(self) -> dict:
        """딕셔너리로 변환."""
        return {
            "posture": self.posture.value,
            "pressures": self.pressures,
            "durations": self.durations,
            "controls": self.controls,
        }


@dataclass
class SensorData:
    """시리얼 장치에서 수신하는 센서 데이터.

    공기가 들어간 zone 리스트를 저장.
    """

    inflated_zones: List[int]  # 공기가 들어간 zone 번호 리스트
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """딕셔너리로 변환."""
        return {
            "inflated_zones": self.inflated_zones,
            "timestamp": self.timestamp.isoformat(),
        }

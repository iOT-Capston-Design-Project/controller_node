"""Domain models for Controller Node."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .enums import ControlAction, ConnectionState, DeviceZone


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
    to the appropriate serial protocol.
    """

    zone: DeviceZone
    action: ControlAction
    intensity: int  # 0-100
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"Zone {self.zone.value}: {self.action.value} at {self.intensity}%"


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

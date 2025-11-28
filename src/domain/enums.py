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
    """Device zones corresponding to body parts.

    Zone mapping (matches master_node BodyPart):
    - Zone 1: Head/Occiput area
    - Zone 2: Scapula/Shoulders area
    - Zone 3: Right elbow area
    - Zone 4: Left elbow area
    - Zone 5: Hip area
    - Zone 6: Right heel area
    - Zone 7: Left heel area
    """

    ZONE_1 = 1  # Head
    ZONE_2 = 2  # Scapula
    ZONE_3 = 3  # Right elbow
    ZONE_4 = 4  # Left elbow
    ZONE_5 = 5  # Hip
    ZONE_6 = 6  # Right heel
    ZONE_7 = 7  # Left heel

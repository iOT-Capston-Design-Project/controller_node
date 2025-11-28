"""Configuration settings for Controller Node."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # Device identification
    device_id: int

    # Master node connection (LAN)
    master_node_address: str
    master_node_port: int

    # Serial communication
    serial_port: str
    serial_baudrate: int

    # Application settings
    cycle_interval: float

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            device_id=int(os.getenv("DEVICE_ID", "1")),
            master_node_address=os.getenv("MASTER_NODE_ADDRESS", "10.0.0.1"),
            master_node_port=int(os.getenv("MASTER_NODE_PORT", "5000")),
            serial_port=os.getenv("SERIAL_PORT", "/dev/ttyUSB0"),
            serial_baudrate=int(os.getenv("SERIAL_BAUDRATE", "115200")),
            cycle_interval=float(os.getenv("CYCLE_INTERVAL", "0.1")),
        )


# Global settings instance
settings = Settings.from_env()

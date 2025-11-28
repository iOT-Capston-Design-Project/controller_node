"""Device interfaces for Controller Node.

This module defines the interface for serial communication with
the physical control device (e.g., air mattress actuators).

The actual implementation will depend on the specific hardware protocol.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain.models import DeviceCommand, DeviceStatus
from ..domain.enums import DeviceZone


class ISerialDevice(ABC):
    """Interface for serial communication with the physical device.

    This is a placeholder interface that should be implemented
    once the actual device protocol is defined.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish serial connection to the device.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close serial connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        pass

    @abstractmethod
    async def send_command(self, command: DeviceCommand) -> bool:
        """Send a single command to the device.

        Args:
            command: The command to execute.

        Returns:
            True if command was acknowledged, False otherwise.
        """
        pass

    @abstractmethod
    async def send_commands(self, commands: List[DeviceCommand]) -> bool:
        """Send multiple commands to the device.

        Args:
            commands: List of commands to execute.

        Returns:
            True if all commands were acknowledged, False otherwise.
        """
        pass

    @abstractmethod
    async def get_status(self) -> DeviceStatus:
        """Query current device status.

        Returns:
            Current status of the device.
        """
        pass

    @abstractmethod
    async def emergency_stop(self) -> bool:
        """Emergency stop all device operations.

        Returns:
            True if stop command was acknowledged.
        """
        pass


class IDeviceProtocol(ABC):
    """Interface for device communication protocol.

    This defines how DeviceCommands are encoded/decoded for
    serial transmission. Implement this based on actual hardware specs.
    """

    @abstractmethod
    def encode_command(self, command: DeviceCommand) -> bytes:
        """Encode a command to bytes for serial transmission.

        Args:
            command: The command to encode.

        Returns:
            Byte sequence to send over serial.
        """
        pass

    @abstractmethod
    def decode_response(self, data: bytes) -> dict:
        """Decode response from device.

        Args:
            data: Raw bytes received from device.

        Returns:
            Parsed response data.
        """
        pass

    @abstractmethod
    def encode_status_request(self) -> bytes:
        """Encode a status query request.

        Returns:
            Byte sequence for status request.
        """
        pass

    @abstractmethod
    def encode_emergency_stop(self) -> bytes:
        """Encode emergency stop command.

        Returns:
            Byte sequence for emergency stop.
        """
        pass

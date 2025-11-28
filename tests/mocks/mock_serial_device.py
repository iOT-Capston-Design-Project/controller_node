"""Mock serial device for testing."""

from datetime import datetime
from typing import List

from src.interfaces.device import ISerialDevice
from src.domain.models import DeviceCommand, DeviceStatus
from src.domain.enums import DeviceZone


class MockSerialDevice(ISerialDevice):
    """Mock implementation of serial device for testing."""

    def __init__(self, should_fail: bool = False):
        """Initialize mock device.

        Args:
            should_fail: If True, commands will fail.
        """
        self._connected = False
        self._should_fail = should_fail
        self._executed_commands: List[DeviceCommand] = []
        self._zone_states = {zone.value: 0 for zone in DeviceZone}

    async def connect(self) -> bool:
        """Connect to mock device."""
        if not self._should_fail:
            self._connected = True
        return self._connected

    async def disconnect(self) -> None:
        """Disconnect from mock device."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def send_command(self, command: DeviceCommand) -> bool:
        """Send command to mock device."""
        if not self._connected or self._should_fail:
            return False

        self._executed_commands.append(command)
        return True

    async def send_commands(self, commands: List[DeviceCommand]) -> bool:
        """Send multiple commands."""
        success = True
        for command in commands:
            if not await self.send_command(command):
                success = False
        return success

    async def get_status(self) -> DeviceStatus:
        """Get device status."""
        return DeviceStatus(
            zone_states=self._zone_states.copy(),
            is_operational=self._connected,
            last_command_success=len(self._executed_commands) > 0,
            error_message=None,
            last_updated=datetime.now(),
        )

    async def emergency_stop(self) -> bool:
        """Emergency stop."""
        self._zone_states = {zone.value: 0 for zone in DeviceZone}
        return True

    # Test helper methods
    def get_executed_commands(self) -> List[DeviceCommand]:
        """Get list of executed commands."""
        return self._executed_commands.copy()

    def clear_commands(self) -> None:
        """Clear executed commands list."""
        self._executed_commands.clear()

    def set_should_fail(self, should_fail: bool) -> None:
        """Set whether commands should fail."""
        self._should_fail = should_fail

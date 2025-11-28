"""Mock display for testing."""

from typing import List, Tuple

from src.interfaces.presentation import IDisplay
from src.domain.models import ControlSignal, DeviceCommand, SystemStatus


class MockDisplay(IDisplay):
    """Mock implementation of display for testing."""

    def __init__(self):
        self._started = False
        self._status_updates: List[SystemStatus] = []
        self._signals_shown: List[ControlSignal] = []
        self._commands_shown: List[List[DeviceCommand]] = []
        self._log_messages: List[Tuple[str, str]] = []  # (message, level)
        self._errors: List[str] = []

    def start(self) -> None:
        """Start mock display."""
        self._started = True

    def stop(self) -> None:
        """Stop mock display."""
        self._started = False

    def update_status(self, status: SystemStatus) -> None:
        """Update status."""
        self._status_updates.append(status)

    def show_signal_received(self, signal: ControlSignal) -> None:
        """Show received signal."""
        self._signals_shown.append(signal)

    def show_commands_executed(self, commands: List[DeviceCommand]) -> None:
        """Show executed commands."""
        self._commands_shown.append(commands)

    def log_message(self, message: str, level: str = "info") -> None:
        """Log message."""
        self._log_messages.append((message, level))

    def show_error(self, error: str) -> None:
        """Show error."""
        self._errors.append(error)

    # Test helper methods
    def is_started(self) -> bool:
        """Check if display is started."""
        return self._started

    def get_status_updates(self) -> List[SystemStatus]:
        """Get status updates."""
        return self._status_updates.copy()

    def get_signals_shown(self) -> List[ControlSignal]:
        """Get shown signals."""
        return self._signals_shown.copy()

    def get_commands_shown(self) -> List[List[DeviceCommand]]:
        """Get shown commands."""
        return self._commands_shown.copy()

    def get_log_messages(self) -> List[Tuple[str, str]]:
        """Get log messages."""
        return self._log_messages.copy()

    def get_errors(self) -> List[str]:
        """Get errors."""
        return self._errors.copy()

    def clear(self) -> None:
        """Clear all recorded data."""
        self._status_updates.clear()
        self._signals_shown.clear()
        self._commands_shown.clear()
        self._log_messages.clear()
        self._errors.clear()

"""Presentation interfaces for Controller Node."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain.models import ControlSignal, DeviceCommand, SystemStatus


class IDisplay(ABC):
    """Interface for system status display."""

    @abstractmethod
    def start(self) -> None:
        """Start the display."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the display."""
        pass

    @abstractmethod
    def update_status(self, status: SystemStatus) -> None:
        """Update system status display.

        Args:
            status: Current system status.
        """
        pass

    @abstractmethod
    def show_signal_received(self, signal: ControlSignal) -> None:
        """Display received control signal.

        Args:
            signal: The received control signal.
        """
        pass

    @abstractmethod
    def show_commands_executed(self, commands: List[DeviceCommand]) -> None:
        """Display executed device commands.

        Args:
            commands: List of executed commands.
        """
        pass

    @abstractmethod
    def log_message(self, message: str, level: str = "info") -> None:
        """Log a message to display.

        Args:
            message: Message to display.
            level: Log level (info, warning, error).
        """
        pass

    @abstractmethod
    def show_error(self, error: str) -> None:
        """Display an error message.

        Args:
            error: Error message to display.
        """
        pass

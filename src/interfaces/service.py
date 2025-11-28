"""Service interfaces for Controller Node."""

from abc import ABC, abstractmethod
from typing import List

from ..domain.models import ControlSignal, DeviceCommand, SystemStatus


class IControlService(ABC):
    """Interface for control signal processing service.

    Converts control signals from master node into device commands.
    """

    @abstractmethod
    def process_signal(self, signal: ControlSignal) -> List[DeviceCommand]:
        """Convert a control signal into device commands.

        Args:
            signal: Control signal from master node.

        Returns:
            List of device commands to execute.
        """
        pass


class IServiceFacade(ABC):
    """Interface for main service orchestration.

    Coordinates between master node communication and device control.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize all services and connections."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        pass

    @abstractmethod
    async def handle_control_signal(self, signal: ControlSignal) -> bool:
        """Process incoming control signal from master node.

        Args:
            signal: Control signal received from master.

        Returns:
            True if signal was processed successfully.
        """
        pass

    @abstractmethod
    def get_system_status(self) -> SystemStatus:
        """Get current system status.

        Returns:
            Current status of all system components.
        """
        pass

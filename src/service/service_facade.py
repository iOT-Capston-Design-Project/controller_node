"""Service facade implementation.

Orchestrates all services and coordinates between master node
communication and device control.
"""

import logging
from datetime import datetime
from typing import Optional

from ..interfaces.service import IServiceFacade, IControlService
from ..interfaces.communication import IMasterNodeClient
from ..interfaces.device import ISerialDevice
from ..interfaces.presentation import IDisplay
from ..domain.models import ControlSignal, SystemStatus
from ..domain.enums import ConnectionState
from ..config.settings import settings

logger = logging.getLogger(__name__)


class ServiceFacade(IServiceFacade):
    """Main service orchestration.

    Coordinates between master node communication and device control.
    """

    def __init__(
        self,
        master_client: IMasterNodeClient,
        serial_device: ISerialDevice,
        control_service: IControlService,
        display: IDisplay,
    ):
        """Initialize service facade.

        Args:
            master_client: Client for master node communication.
            serial_device: Serial device for hardware control.
            control_service: Service for processing control signals.
            display: Display for status output.
        """
        self._master_client = master_client
        self._serial_device = serial_device
        self._control_service = control_service
        self._display = display

        # Status tracking
        self._last_signal_received: Optional[datetime] = None
        self._last_command_executed: Optional[datetime] = None
        self._commands_executed = 0
        self._errors_count = 0

    async def initialize(self) -> None:
        """Initialize all services and connections."""
        logger.info("Initializing services...")

        # Set up signal handler for master node
        self._master_client.set_signal_handler(self.handle_control_signal)

        # Start master node server
        await self._master_client.start()
        self._display.log_message(
            f"TCP server started on port {settings.master_node_port}"
        )

        # Connect to serial device
        if await self._serial_device.connect():
            self._display.log_message("Serial device connected")
        else:
            self._display.log_message("Serial device connection failed", level="warning")

        # Start display
        self._display.start()

        # Update initial status
        self._display.update_status(self.get_system_status())

        logger.info("Services initialized")

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Shutting down services...")

        # Stop display
        self._display.stop()

        # Disconnect serial device
        await self._serial_device.disconnect()

        # Stop master node server
        await self._master_client.stop()

        logger.info("Services shut down")

    async def handle_control_signal(self, signal: ControlSignal) -> bool:
        """Process incoming control signal from master node.

        Args:
            signal: Control signal received from master.

        Returns:
            True if signal was processed successfully.
        """
        self._last_signal_received = datetime.now()
        logger.info(
            f"Received signal: zones={signal.target_zones}, "
            f"action={signal.action.value}, intensity={signal.intensity}"
        )

        # Display received signal
        self._display.show_signal_received(signal)

        # Convert signal to device commands
        commands = self._control_service.process_signal(signal)

        if not commands:
            logger.debug("No commands to execute")
            self._display.update_status(self.get_system_status())
            return True

        # Execute commands on device
        success = await self._serial_device.send_commands(commands)

        if success:
            self._last_command_executed = datetime.now()
            self._commands_executed += len(commands)
            self._display.show_commands_executed(commands)
            logger.info(f"Executed {len(commands)} commands successfully")
        else:
            self._errors_count += 1
            self._display.show_error("Failed to execute device commands")
            logger.error("Failed to execute device commands")

        # Update display
        self._display.update_status(self.get_system_status())

        return success

    def get_system_status(self) -> SystemStatus:
        """Get current system status.

        Returns:
            Current status of all system components.
        """
        # Determine connection states
        master_state = (
            ConnectionState.CONNECTED
            if self._master_client.is_connected()
            else ConnectionState.DISCONNECTED
        )

        serial_state = (
            ConnectionState.CONNECTED
            if self._serial_device.is_connected()
            else ConnectionState.DISCONNECTED
        )

        return SystemStatus(
            device_id=settings.device_id,
            master_connection=master_state,
            serial_connection=serial_state,
            last_signal_received=self._last_signal_received,
            last_command_executed=self._last_command_executed,
            commands_executed=self._commands_executed,
            errors_count=self._errors_count,
        )

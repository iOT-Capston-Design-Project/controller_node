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
from ..domain.models import ControlSignal, ControlPacket, SystemStatus
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
        self._last_packet: Optional[ControlPacket] = None
        self._sensor_send_task = None

    async def initialize(self) -> None:
        """Initialize all services and connections."""
        logger.info("Initializing services...")

        # Set up signal handler for master node
        self._master_client.set_signal_handler(self.handle_control_signal)
        self._master_client.set_packet_handler(self.handle_control_packet)

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

        # Start sensor data send loop
        import asyncio
        self._sensor_send_task = asyncio.create_task(self._sensor_data_loop())

        # Update initial status
        self._display.update_status(self.get_system_status())

        logger.info("Services initialized")

    async def _sensor_data_loop(self) -> None:
        """Periodically check and send sensor data to master node."""
        import asyncio
        while True:
            try:
                sensor_data = self._serial_device.get_sensor_data()
                if sensor_data:
                    if await self._master_client.send_sensor_data(sensor_data):
                        self._display.log_message(
                            f"센서 데이터 전송: zones={sensor_data.inflated_zones}", level="info"
                        )
                await asyncio.sleep(0.1)  # 100ms 주기로 확인
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sensor data loop error: {e}")

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Shutting down services...")

        # Stop sensor data loop
        if self._sensor_send_task:
            self._sensor_send_task.cancel()
            try:
                await self._sensor_send_task
            except:
                pass

        # Stop display
        self._display.stop()

        # Disconnect serial device
        await self._serial_device.disconnect()

        # Stop master node server
        await self._master_client.stop()

        logger.info("Services shut down")

    async def handle_control_packet(self, packet: ControlPacket) -> bool:
        """Process incoming control packet from master node.

        Args:
            packet: Control packet received from master.

        Returns:
            True if packet was processed successfully.
        """
        self._last_signal_received = datetime.now()
        self._last_packet = packet
        logger.info(
            f"Received packet: posture={packet.posture.value}, "
            f"pressures={packet.pressures}, durations={packet.durations}"
        )

        # Display received packet
        self._display.show_packet_received(packet)

        # Update display
        self._display.update_status(self.get_system_status())

        return True

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

"""Service facade implementation.

Orchestrates all services and coordinates between master node
communication and device control.
"""

import logging
from datetime import datetime
from typing import List, Optional

from ..interfaces.service import IServiceFacade, IControlService
from ..interfaces.communication import IMasterNodeClient
from ..interfaces.device import ISerialDevice
from ..interfaces.presentation import IDisplay
from ..domain.models import ControlSignal, ControlPacket, SystemStatus
from ..domain.enums import ConnectionState
from ..config.settings import settings
from .zone_priority import ZonePriorityService

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

        # 압력 기반 존 순서 결정 서비스
        self._zone_priority = ZonePriorityService()

        # 마지막으로 전송한 zone 순서 (중복 체크용)
        # Arduino에서도 중복 체크하지만, 불필요한 통신 줄이기 위해 여기서도 체크
        self._last_zone_sequence: Optional[List[int]] = None

        # 에어셀 활성화 상태 추적 (상태 변경 시에만 명령 전송)
        self._air_activated: bool = False

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

        # Emergency stop Arduino (stops sequence, clears queue)
        await self._serial_device.emergency_stop()

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

        압력값과 지속시간을 기반으로 존 순서를 결정하고
        Arduino에 시퀀스 명령을 전송하여 순차적으로 inflate/deflate 실행.
        activate_air가 false면 아두이노를 정지시킴.

        Args:
            packet: Control packet received from master.

        Returns:
            True if packet was processed successfully.
        """
        self._last_signal_received = datetime.now()
        self._last_packet = packet
        logger.info(
            f"Received packet: posture={packet.posture.value}, "
            f"pressures={packet.pressures}, durations={packet.durations}, "
            f"activate_air={packet.activate_air}"
        )

        # Display received packet
        self._display.show_packet_received(packet)

        # activate_air 상태 로깅
        logger.info(
            f"activate_air state: packet={packet.activate_air}, "
            f"current={self._air_activated}"
        )

        # activate_air 상태 변경 확인 및 처리
        if packet.activate_air != self._air_activated:
            if packet.activate_air:
                # 비활성화 -> 활성화: 시퀀스 시작 가능 상태로 전환
                logger.info("Air activation enabled - Arduino can now receive sequences")
                self._display.log_message("에어셀 활성화됨", level="info")
                self._air_activated = True
                # 이전 시퀀스 초기화 (새로 시작하므로)
                self._last_zone_sequence = None
            else:
                # 활성화 -> 비활성화: 아두이노 정지
                logger.info("Air activation disabled - Stopping Arduino")
                self._display.log_message("에어셀 비활성화 - Arduino 정지", level="warning")
                await self._serial_device.emergency_stop()
                self._air_activated = False
                self._last_zone_sequence = None
                # 비활성화 상태에서는 시퀀스 전송하지 않음
                self._display.update_status(self.get_system_status())
                return True

        # activate_air가 false면 시퀀스 전송하지 않음
        if not packet.activate_air:
            logger.info("Air not activated, skipping sequence")
            self._display.update_status(self.get_system_status())
            return True

        logger.info("Air is activated, proceeding with zone sequence...")

        # 서버 강제 순서 확인 (controls.orders)
        forced_orders = None
        if packet.controls and isinstance(packet.controls, dict):
            forced_orders = packet.controls.get("orders")
            if forced_orders:
                logger.info(f"Server forced zone order: {forced_orders}")

        # 압력 기반 존 순서 결정 (강제 순서가 있으면 우선 적용)
        zone_sequence = self._zone_priority.determine_zone_order(
            pressures=packet.pressures,
            durations=packet.durations,
            posture=packet.posture,
            forced_orders=forced_orders,
        )

        if zone_sequence:
            # zone_sequence는 [(zone_num, duration), ...] 형태
            # Arduino에는 zone 번호만 전송 (duration은 Arduino에서 고정값 사용)
            zone_numbers = [z[0] for z in zone_sequence]

            # 중복 체크: 같은 순서면 무시 (불필요한 통신 방지)
            if zone_numbers == self._last_zone_sequence:
                logger.info(f"Duplicate zone sequence ignored: {zone_numbers}")
                self._display.log_message(
                    f"중복 순서 무시: {zone_numbers}", level="debug"
                )
            else:
                logger.info(f"Sending zone sequence to Arduino: {zone_numbers}")
                self._display.log_message(
                    f"Arduino 시퀀스 전송: {zone_numbers}", level="info"
                )

                # Arduino에 시퀀스 전송 (Arduino가 큐잉/중복체크 처리)
                success = await self._serial_device.send_sequence(zone_numbers)

                if success:
                    self._last_zone_sequence = zone_numbers
                    self._last_command_executed = datetime.now()
                    self._commands_executed += 1
                else:
                    self._errors_count += 1
                    self._display.show_error("Failed to send sequence to Arduino")
        else:
            logger.debug("No zones require relief based on pressure data")

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

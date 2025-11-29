"""Mock serial device with random sensor data generation for test mode."""

import asyncio
import logging
import random
from datetime import datetime
from typing import List, Optional

from ..interfaces.device import ISerialDevice
from ..domain.models import DeviceCommand, DeviceStatus, SensorData
from ..domain.enums import DeviceZone

logger = logging.getLogger(__name__)


class MockSerialDeviceWithSensorData(ISerialDevice):
    """시리얼 장치 모킹 + 임의 센서 데이터 생성.

    테스트 모드에서 실제 시리얼 장치 없이 임의의 센서 데이터를 생성하여
    마스터 노드에게 전송할 수 있도록 합니다.
    """

    def __init__(
        self,
        sensor_interval: float = 1.0,
        min_zones: int = 0,
        max_zones: int = 4,
    ):
        """Initialize mock device.

        Args:
            sensor_interval: 센서 데이터 생성 주기 (초).
            min_zones: 최소 활성 존 개수.
            max_zones: 최대 활성 존 개수.
        """
        self._connected = False
        self._executed_commands: List[DeviceCommand] = []
        self._zone_states = {zone.value: 0 for zone in DeviceZone}

        # Sensor data generation settings
        self._sensor_interval = sensor_interval
        self._min_zones = min_zones
        self._max_zones = max_zones

        # Sensor data queue
        self._sensor_data: Optional[SensorData] = None
        self._sensor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def connect(self) -> bool:
        """Connect to mock device and start sensor data generation."""
        self._connected = True
        self._stop_event.clear()

        # Start sensor data generation task
        self._sensor_task = asyncio.create_task(self._generate_sensor_data_loop())
        logger.info("MockSerialDevice 연결됨 (테스트 모드 - 임의 센서 데이터 생성 시작)")
        return True

    async def disconnect(self) -> None:
        """Disconnect and stop sensor data generation."""
        self._stop_event.set()

        if self._sensor_task:
            self._sensor_task.cancel()
            try:
                await self._sensor_task
            except asyncio.CancelledError:
                pass

        self._connected = False
        logger.info("MockSerialDevice 연결 해제됨")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def _generate_sensor_data_loop(self) -> None:
        """Background task to generate random sensor data."""
        all_zones = [zone.value for zone in DeviceZone]  # [1, 2, 3, 4]

        while not self._stop_event.is_set():
            try:
                # 랜덤하게 활성 존 선택
                num_active = random.randint(self._min_zones, self._max_zones)
                active_zones = sorted(random.sample(all_zones, num_active))

                self._sensor_data = SensorData(
                    inflated_zones=active_zones,
                    timestamp=datetime.now(),
                )

                logger.debug(f"[테스트] 센서 데이터 생성: zones={active_zones}")

                await asyncio.sleep(self._sensor_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"센서 데이터 생성 오류: {e}")
                await asyncio.sleep(1.0)

    def get_sensor_data(self) -> Optional[SensorData]:
        """Get latest generated sensor data.

        Returns:
            Latest sensor data or None if no data available.
        """
        data = self._sensor_data
        self._sensor_data = None  # 한 번 읽으면 클리어
        return data

    def has_sensor_data(self) -> bool:
        """Check if there is sensor data available."""
        return self._sensor_data is not None

    async def send_command(self, command: DeviceCommand) -> bool:
        """Send command to mock device (always succeeds)."""
        if not self._connected:
            return False

        self._executed_commands.append(command)
        logger.info(f"[테스트] 명령 수신: {command}")
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
        logger.warning("[테스트] 긴급 정지 실행")
        return True

    # Test helper methods
    def get_executed_commands(self) -> List[DeviceCommand]:
        """Get list of executed commands."""
        return self._executed_commands.copy()

    def clear_commands(self) -> None:
        """Clear executed commands list."""
        self._executed_commands.clear()

    def set_sensor_interval(self, interval: float) -> None:
        """Set sensor data generation interval.

        Args:
            interval: 센서 데이터 생성 주기 (초).
        """
        self._sensor_interval = interval

    def set_zone_range(self, min_zones: int, max_zones: int) -> None:
        """Set random zone range.

        Args:
            min_zones: 최소 활성 존 개수.
            max_zones: 최대 활성 존 개수.
        """
        self._min_zones = min_zones
        self._max_zones = max_zones

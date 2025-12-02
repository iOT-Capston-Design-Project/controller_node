"""Mock serial device with random sensor data generation for test mode."""

import asyncio
import logging
import random
import threading
from datetime import datetime
from queue import Queue, Empty
from typing import List, Optional

import serial

from ..interfaces.device import ISerialDevice, IDeviceProtocol
from ..domain.models import DeviceCommand, DeviceStatus, SensorData
from ..domain.enums import DeviceZone, ControlAction
from ..config.settings import settings

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


class TestSerialProtocol(IDeviceProtocol):
    """테스트용 아두이노 프로토콜.

    Commands:
    - SEQ:<z1>,<z2>,...\n : Start sequence pattern
    - QUEUE:<z1>,<z2>,...\n : Queue next sequence
    - P : Pause/Emergency stop
    - STATUS : Query current state
    """

    def encode_command(self, command: DeviceCommand) -> bytes:
        """Encode command to bytes."""
        return f"Z{command.zone.value}:{command.action.value}\n".encode()

    def decode_response(self, data: bytes) -> dict:
        """Decode response from device."""
        try:
            response = data.decode("utf-8", errors="ignore").strip()
            if not response:
                return {"success": True, "message": ""}
            if response.startswith("OK"):
                return {"success": True, "message": response}
            elif response.startswith("ERR:"):
                return {"success": False, "error": response[4:]}
            else:
                return {"success": True, "message": response, "is_log": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def encode_status_request(self) -> bytes:
        """Encode status query."""
        return b"STATUS\n"

    def encode_emergency_stop(self) -> bytes:
        """Encode emergency stop."""
        return b"P"

    def encode_sequence(self, zones: List[int]) -> bytes:
        """Encode sequence pattern command.

        Args:
            zones: List of zone numbers (1-indexed) e.g., [1, 2, 3]

        Returns:
            Encoded command bytes e.g., b"SEQ:1,2,3\n"
        """
        zones_str = ",".join(str(z) for z in zones)
        return f"SEQ:{zones_str}\n".encode()


class SerialTestDevice(ISerialDevice):
    """실제 시리얼 통신 + 시퀀스 테스트 명령 자동 전송.

    아두이노와 실제 시리얼 통신을 수행하면서
    주기적으로 SEQ 명령을 자동 전송합니다.
    """

    # 테스트용 시퀀스 패턴들 (순환)
    TEST_SEQUENCES = [
        [1, 2, 3, 4],  # 전체 순환
        [1, 3],        # 대각선 1
        [2, 4],        # 대각선 2
        [1, 2],        # 상단
        [3, 4],        # 하단
    ]

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        test_interval: float = 30.0,
    ):
        """Initialize test serial device.

        Args:
            port: 시리얼 포트 경로 (기본: settings에서 로드).
            baudrate: 보드레이트 (기본: settings에서 로드).
            test_interval: 시퀀스 변경 주기 (초, 기본: 30초).
        """
        self._port = port or settings.serial_port
        self._baudrate = baudrate or settings.serial_baudrate
        self._protocol = TestSerialProtocol()
        self._connected = False
        self._serial: Optional[serial.Serial] = None

        # Device state
        self._zone_states: dict = {zone.value: 0 for zone in DeviceZone}
        self._last_command_success = True
        self._error_message: Optional[str] = None

        # Reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()
        self._response_queue: Queue = Queue()
        self._log_queue: Queue = Queue()
        self._sensor_data_queue: Queue = Queue()

        # Test mode settings
        self._test_interval = test_interval
        self._test_task: Optional[asyncio.Task] = None
        self._test_sequence_index = 0

    def _reader_loop(self) -> None:
        """Background thread to read Arduino serial output."""
        while not self._stop_reader.is_set():
            try:
                if self._serial and self._serial.is_open:
                    line = self._serial.readline()
                    if line:
                        decoded = line.decode("utf-8", errors="ignore").strip()
                        if decoded:
                            logger.info(f"[Arduino] {decoded}")

                            # 센서 데이터 파싱 (ZONES:1,2,3 형식)
                            if decoded.startswith("ZONES:"):
                                zones_str = decoded[6:]
                                if zones_str:
                                    inflated_zones = [
                                        int(z.strip())
                                        for z in zones_str.split(",")
                                        if z.strip()
                                    ]
                                else:
                                    inflated_zones = []
                                sensor_data = SensorData(inflated_zones=inflated_zones)
                                self._sensor_data_queue.put(sensor_data)
                                logger.debug(f"센서 데이터 수신: zones={inflated_zones}")
                                continue

                            # JSON 센서 데이터 파싱
                            if decoded.startswith("{") and "inflated_zones" in decoded:
                                try:
                                    import json
                                    sensor_json = json.loads(decoded)
                                    sensor_data = SensorData(
                                        inflated_zones=sensor_json.get("inflated_zones", [])
                                    )
                                    self._sensor_data_queue.put(sensor_data)
                                    continue
                                except:
                                    pass

                            # 응답 파싱
                            result = self._protocol.decode_response(line)
                            if result.get("is_log"):
                                self._log_queue.put(decoded)
                            else:
                                self._response_queue.put(result)

            except serial.SerialException as e:
                logger.error(f"시리얼 읽기 오류: {e}")
                self._stop_reader.set()
                break
            except Exception as e:
                logger.error(f"Reader 오류: {e}")

    async def connect(self) -> bool:
        """시리얼 연결 및 테스트 루프 시작."""
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=1.0,
            )

            # 아두이노 리셋 대기
            await asyncio.sleep(2.0)

            # Reader 스레드 시작
            self._stop_reader.clear()
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()

            # 테스트 루프 시작
            self._test_task = asyncio.create_task(self._test_command_loop())

            logger.info(f"테스트 시리얼 연결됨: {self._port} @ {self._baudrate} baud")
            self._connected = True
            return True

        except serial.SerialException as e:
            logger.error(f"시리얼 연결 실패: {e}")
            self._error_message = str(e)
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"연결 오류: {e}")
            self._error_message = str(e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """연결 해제."""
        # 테스트 루프 중지
        if self._test_task:
            self._test_task.cancel()
            try:
                await self._test_task
            except asyncio.CancelledError:
                pass

        # Reader 스레드 중지
        self._stop_reader.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)

        if self._serial and self._serial.is_open:
            self._serial.close()

        self._serial = None
        self._connected = False
        logger.info("테스트 시리얼 연결 해제됨")

    def is_connected(self) -> bool:
        """연결 상태 확인."""
        return self._connected and self._serial is not None and self._serial.is_open

    async def _test_command_loop(self) -> None:
        """테스트 시퀀스 명령 자동 전송 루프.

        TEST_SEQUENCES에 정의된 패턴들을 순환하며 SEQ 명령 전송.
        """
        while self._connected:
            try:
                # 현재 시퀀스 패턴
                zones = self.TEST_SEQUENCES[self._test_sequence_index]

                logger.info(f"[테스트] 시퀀스 전송: SEQ:{','.join(map(str, zones))}")
                await self.send_sequence(zones)

                # 다음 시퀀스로
                self._test_sequence_index = (self._test_sequence_index + 1) % len(self.TEST_SEQUENCES)

                await asyncio.sleep(self._test_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"테스트 루프 오류: {e}")
                await asyncio.sleep(1.0)

    async def send_sequence(self, zones: List[int]) -> bool:
        """시퀀스 패턴 명령 전송.

        Args:
            zones: Zone 번호 리스트 (1-indexed) e.g., [1, 2, 3]

        Returns:
            True if command was sent successfully.
        """
        if not self.is_connected():
            logger.error("시퀀스 전송 실패: 연결되지 않음")
            return False

        if not zones:
            logger.warning("빈 시퀀스, 전송 생략")
            return False

        try:
            data = self._protocol.encode_sequence(zones)
            logger.debug(f"전송: {data.decode().strip()}")
            self._serial.write(data)

            # 응답 대기
            try:
                response = self._response_queue.get(timeout=2.0)
                if response.get("success"):
                    logger.info(f"시퀀스 전송 성공: {zones} - {response.get('message', 'OK')}")
                    self._last_command_success = True
                    return True
                else:
                    self._error_message = response.get("error", "Unknown error")
                    logger.error(f"시퀀스 전송 실패: {self._error_message}")
                    self._last_command_success = False
                    return False
            except Empty:
                # 응답 없음 - 성공으로 간주
                logger.info(f"시퀀스 전송 (응답 없음): {zones}")
                self._last_command_success = True
                return True

        except Exception as e:
            logger.error(f"시퀀스 전송 오류: {e}")
            self._error_message = str(e)
            self._last_command_success = False
            return False

    async def send_command(self, command: DeviceCommand) -> bool:
        """명령 전송."""
        if not self.is_connected():
            logger.error("명령 전송 실패: 연결되지 않음")
            return False

        try:
            data = self._protocol.encode_command(command)
            logger.debug(f"전송: {data.decode().strip()}")
            self._serial.write(data)

            # 응답 대기
            try:
                response = self._response_queue.get(timeout=2.0)
                if response.get("success"):
                    if command.action == ControlAction.INFLATE:
                        self._zone_states[command.zone.value] = 1
                    elif command.action == ControlAction.DEFLATE:
                        self._zone_states[command.zone.value] = 0

                    logger.info(f"명령 성공: {command}")
                    self._last_command_success = True
                    return True
                else:
                    self._error_message = response.get("error", "Unknown error")
                    logger.error(f"명령 실패: {self._error_message}")
                    self._last_command_success = False
                    return False
            except Empty:
                # 응답 없음 - 성공으로 간주
                if command.action == ControlAction.INFLATE:
                    self._zone_states[command.zone.value] = 1
                elif command.action == ControlAction.DEFLATE:
                    self._zone_states[command.zone.value] = 0

                logger.info(f"명령 전송 (응답 없음): {command}")
                self._last_command_success = True
                return True

        except Exception as e:
            logger.error(f"명령 전송 오류: {e}")
            self._error_message = str(e)
            self._last_command_success = False
            return False

    async def send_commands(self, commands: List[DeviceCommand]) -> bool:
        """여러 명령 전송."""
        success = True
        for command in commands:
            if not await self.send_command(command):
                success = False
        return success

    async def get_status(self) -> DeviceStatus:
        """장치 상태 조회."""
        return DeviceStatus(
            zone_states=self._zone_states.copy(),
            is_operational=self.is_connected(),
            last_command_success=self._last_command_success,
            error_message=self._error_message,
            last_updated=datetime.now(),
        )

    async def emergency_stop(self) -> bool:
        """긴급 정지."""
        if not self.is_connected():
            return False

        try:
            self._serial.write(self._protocol.encode_emergency_stop())
            self._zone_states = {zone.value: 0 for zone in DeviceZone}
            logger.warning("긴급 정지 실행")
            return True
        except Exception as e:
            logger.error(f"긴급 정지 실패: {e}")
            return False

    def get_sensor_data(self) -> Optional[SensorData]:
        """최신 센서 데이터 반환."""
        latest_data = None
        while not self._sensor_data_queue.empty():
            try:
                latest_data = self._sensor_data_queue.get_nowait()
            except Empty:
                break
        return latest_data

    def has_sensor_data(self) -> bool:
        """센서 데이터 존재 여부."""
        return not self._sensor_data_queue.empty()

    def get_recent_logs(self, max_count: int = 10) -> List[str]:
        """최근 로그 메시지."""
        logs = []
        while not self._log_queue.empty() and len(logs) < max_count:
            try:
                logs.append(self._log_queue.get_nowait())
            except Empty:
                break
        return logs

    def set_test_interval(self, interval: float) -> None:
        """테스트 명령 전송 주기 설정."""
        self._test_interval = interval

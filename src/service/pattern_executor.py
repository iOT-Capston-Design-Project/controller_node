"""Pattern executor for time-based sequential zone control.

Executes inflate/deflate sequences on zones with specified durations.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Tuple, Optional

from ..domain.models import DeviceCommand
from ..domain.enums import DeviceZone, ControlAction
from ..interfaces.device import ISerialDevice

logger = logging.getLogger(__name__)


class PatternExecutor:
    """시간 기반 순차 패턴 실행.

    각 존에 대해 inflate → 지정 시간 대기 → deflate 순서로 실행.
    """

    # 존 간 전환 시 대기 시간 (초)
    ZONE_TRANSITION_DELAY = 0.5

    def __init__(self, serial_device: ISerialDevice):
        """Initialize pattern executor.

        Args:
            serial_device: 시리얼 장치 인터페이스
        """
        self._device = serial_device
        self._running = False
        self._current_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """패턴 실행 중 여부."""
        return self._running

    async def execute_sequence(
        self,
        zone_sequence: List[Tuple[int, int]],
    ) -> bool:
        """존 순서대로 순차 실행.

        각 존에 대해:
        1. Inflate 명령 전송
        2. 지정된 시간 대기
        3. Deflate 명령 전송
        4. 다음 존으로 이동

        Args:
            zone_sequence: [(존번호, 지속시간초), ...]
                예: [(2, 15), (1, 10), (4, 5)]
                → Zone 2: 15초, Zone 1: 10초, Zone 4: 5초

        Returns:
            True if sequence completed successfully, False otherwise.
        """
        if not zone_sequence:
            logger.debug("Empty zone sequence, nothing to execute")
            return True

        if self._running:
            logger.warning("Pattern already running, stopping previous")
            await self.stop()

        self._running = True
        logger.info(f"Starting pattern sequence: {zone_sequence}")

        try:
            for zone_num, duration in zone_sequence:
                if not self._running:
                    logger.info("Sequence stopped by external request")
                    break

                # 존 번호 유효성 검사
                try:
                    zone = DeviceZone(zone_num)
                except ValueError:
                    logger.warning(f"Invalid zone number: {zone_num}, skipping")
                    continue

                logger.info(f"Zone {zone_num}: inflating for {duration}s")

                # 1) Inflate 명령
                inflate_cmd = DeviceCommand(
                    zone=zone,
                    action=ControlAction.INFLATE,
                    timestamp=datetime.now(),
                )
                success = await self._device.send_command(inflate_cmd)
                if not success:
                    logger.error(f"Failed to inflate zone {zone_num}")
                    continue

                # 2) 지정 시간 대기
                try:
                    await asyncio.sleep(duration)
                except asyncio.CancelledError:
                    logger.info("Sleep cancelled during inflate")
                    # Deflate before exit
                    await self._deflate_zone(zone)
                    raise

                if not self._running:
                    await self._deflate_zone(zone)
                    break

                # 3) Deflate 명령
                await self._deflate_zone(zone)
                logger.info(f"Zone {zone_num}: deflated")

                # 4) 존 전환 대기
                if self._running:
                    await asyncio.sleep(self.ZONE_TRANSITION_DELAY)

            logger.info("Pattern sequence completed")
            return True

        except asyncio.CancelledError:
            logger.info("Pattern sequence cancelled")
            return False
        except Exception as e:
            logger.error(f"Pattern sequence failed: {e}")
            return False
        finally:
            self._running = False

    async def _deflate_zone(self, zone: DeviceZone) -> bool:
        """존 deflate 실행.

        Args:
            zone: deflate할 존

        Returns:
            True if successful.
        """
        deflate_cmd = DeviceCommand(
            zone=zone,
            action=ControlAction.DEFLATE,
            timestamp=datetime.now(),
        )
        return await self._device.send_command(deflate_cmd)

    async def stop(self) -> None:
        """패턴 실행 중단.

        현재 실행 중인 시퀀스를 중단하고 긴급 정지 실행.
        """
        logger.info("Stopping pattern execution")
        self._running = False

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        # 긴급 정지로 모든 존 deflate
        await self._device.emergency_stop()
        logger.info("Pattern stopped, emergency stop executed")

    def start_background(
        self,
        zone_sequence: List[Tuple[int, int]],
    ) -> asyncio.Task:
        """백그라운드에서 패턴 실행.

        Args:
            zone_sequence: [(존번호, 지속시간초), ...]

        Returns:
            실행 중인 asyncio Task
        """
        self._current_task = asyncio.create_task(
            self.execute_sequence(zone_sequence)
        )
        return self._current_task
